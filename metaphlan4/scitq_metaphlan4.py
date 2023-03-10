from scitq.lib import Server
from scitq.fetch import get_s3
import subprocess
import argparse
import os


# Do not change that unless you know what you do
DOCKER = 'gmtscience/metaphlan{major_version}:{version}'
DEFAULT_VERSION = '4.0.6'
DEFAULT_WORKERS = 5
DEFAULT_REGION = 'GRA11'

MAX_RETRY_PHASE1 = 2
MAX_RETRY_PHASE2 = 5

def metaphlan4(scitq_server, batch, source_s3, output_s3, final_output_s3, metaphlan_s3,
        region=DEFAULT_REGION, workers=DEFAULT_WORKERS, metaphlan_version=DEFAULT_VERSION):
    """Launch biomscope using scitq in two phase, final compilation is done locally.
    Requires awscli, awscli-plugin-endpoint, combine_csv, sed and cut. Paramaters are
    explained through commande line --help"""

    s=Server(scitq_server, style='object')

    # remove trailing slash
    source_s3 = source_s3.rstrip('/')
    output_s3 = output_s3.rstrip('/')
    if not(output_s3.startswith('s3://')):
        raise RuntimeError(f'output_s3 should be in the form s3://bucket/path... and not {output_s3}')

    if not (metaphlan_s3.endswith('.tar.gz') or metaphlan_s3.endswith('.tgz')):
        raise RuntimeError(f'metaphlan_s3 should be in the form s3://bucket/path.../whatever.tgz (or .tar.gz) and not {metaphlan_s3}')


    source_s3_l = source_s3.split('/')
    if source_s3_l[0]!='s3' and source_s3_l[1]!='' and len(source_s3_l)<3:
        raise RuntimeError(f'source_s3 should be in the form s3://bucket/path... and not {source_s3}')
    bucket = source_s3_l[2]
    source_path = '/'.join(source_s3_l[3:])

    s3 = get_s3()
    bucket_obj = s3.Bucket(bucket)
    fastqs = [fastq.key for fastq in 
                bucket_obj.objects.filter(Prefix=source_path) if fastq.key.endswith('fastq.gz')]
    
    # fastqs are supposed to be grouped in folders each folder representing a sample
    samples = {}
    for fastq in fastqs:
        sample = fastq.split('/')[-2]
        fastq = f's3://{bucket}/{fastq}'
        if sample not in samples:
            samples[sample]=[fastq]
        else:
            samples[sample].append(fastq)

    major_version = metaphlan_version.split('.')[0]
    docker = DOCKER.format(version=metaphlan_version, major_version=major_version)

    if major_version=='3':
        command=f"""sh -c 'zcat /input/*.fastq.gz |metaphlan --input_type fastq \
    --no_map --bowtie2db /resource/metaphlan/bowtie2 \
    --nproc $CPU -o /output/{sample}.metaphlan4_profile.txt' """
    else:
        command=f"""sh -c 'zcat /input/*.fastq.gz |metaphlan --input_type fastq \
    --no_map --offline --bowtie2db /resource/metaphlan/bowtie2 \
    --nproc $CPU -o /output/{sample}.metaphlan4_profile.txt' """

    tasks = []
    for sample,fastqs in samples.items():
        tasks.append(
            s.task_create(
                command=command,
                name=sample,
                batch=batch+'_metaphlan4',
                input=' '.join(fastqs),
                output=f'{output_s3}/{sample}',
                resource=f'{metaphlan_s3}|untar',
                container=docker
            )
        )
    s.worker_deploy(number=workers,
        batch=batch+'_metaphlan4',
        region=region,
        flavor='c2-120',
        concurrency=4,
        prefetch=1)
    s.join(tasks, retry=MAX_RETRY_PHASE1)

    if metaphlan_version in ['4.0.1','4.0.3','4.0.3.1']:
        command = """sh -c "
cd /input
merge_metaphlan_tables.py */*profile.txt > /output/merged_abundance_table.tsv
for sample in *
do
    sgb_to_gtdb_profile.py -i ${sample}/${sample}.metaphlan4_profile.txt -o ${sample}/${sample}.metaphlan4_profile.txt.gtdb
done
combine_csv -c -a -s '\t' -i '*/*profile.txt.gtdb' -o /output/merged_abundance_table_gtdb.tsv
" """
    elif metaphlan_version in ['4.0.6']:
        command = """sh -c "
cd /input
merge_metaphlan_tables.py */*profile.txt > /output/merged_abundance_table.tsv
for sample in *
do
    sgb_to_gtdb_profile.py -d /resource/metaphlan/bowtie2/*.pkl -i ${sample}/${sample}.metaphlan4_profile.txt -o ${sample}/${sample}.metaphlan4_profile.txt.gtdb
done
combine_csv -c -a -s '\t' -i '*/*profile.txt.gtdb' -o /output/merged_abundance_table_gtdb.tsv
" """
    else:
        command = """sh -c "
cd /input
merge_metaphlan_tables.py */*profile.txt > /output/merged_abundance_table.tsv
" """

    task=s.task_create(
            name = batch,
            batch = batch+'_metaphlan4_p2',
            input = output_s3+'/',
            container = docker,
            output = final_output_s3,
            command = command
        )
    
    s.worker_deploy(number=1,
        batch=batch+'_metaphlan4_p2',
        region=region,
        flavor='c2-30',
        concurrency=1,
        prefetch=1)

    s.join([task], retry=MAX_RETRY_PHASE2)

    subprocess.run([f'aws s3 sync {final_output_s3} {batch}'], shell=True, check=True)


if __name__=='__main__':
    SCITQ_SERVER = os.environ.get('SCITQ_SERVER')
    parser = argparse.ArgumentParser(
                    prog = 'SCITQ Metaphlan4',
                    description = 'Launch a Metaphlan4 analysis on some paired FASTQs from WGS samples. Will create a directory with synthetic TSV files.')
    parser.add_argument('batch', type=str, 
        help='A short name for this project')
    parser.add_argument('source_s3', type=str, 
        help="S3 path where the FASTQs are in the form s3://bucket/path... FASTQs should be grouped per sample in a folder named after the sample")
    parser.add_argument('output_s3', type=str, 
        help='a (temporary) S3 folder where Metaphlan4 raw results will be stored')
    parser.add_argument('final_output_s3', type=str, 
        help='a (temporary) S3 folder where Metaphlan4 synthetic results will be stored')
    
    parser.add_argument('metaphlan_s3', type=str, 
        help='An S3 file path for metaphlan4 databases, metaphlan4.tgz, which can be downloaded from Zenodo: https://zenodo.org/record/7537081#.Y8LBN6fP1Bs')
    parser.add_argument('--scitq', type=str, 
        help=f'SCITQ server FQDN, default to {SCITQ_SERVER}', default=SCITQ_SERVER)
    parser.add_argument('--region', type=str, 
        help=f'Provider region - default to {DEFAULT_REGION}', default=DEFAULT_REGION)
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS,
        help=f'how many workers should we have, default to {DEFAULT_WORKERS}.')
    parser.add_argument('--metaphlan-version', type=str, default='4.0.6',
        help=f'what version of metaphlan should be used (3.1.0, 4.0.3, 4.0.5 or 4.0.6)')
    args = parser.parse_args()

    if not args.scitq:
        raise RuntimeError('You must define which SCITQ server we use, either defining SCITQ_SERVER environment variable or using --scitq')


    metaphlan4(
        batch=args.batch,
        scitq_server=args.scitq,

        source_s3=args.source_s3,
        output_s3=args.output_s3,
        final_output_s3=args.final_output_s3,
        metaphlan_s3=args.metaphlan_s3,

        region=args.region,
        workers=args.workers,
        metaphlan_version=args.metaphlan_version
    )