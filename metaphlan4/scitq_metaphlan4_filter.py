from scitq.lib import Server
from scitq.fetch import sync, list_content
import subprocess
import argparse
import os


# Do not change that unless you know what you do
DOCKER = 'gmtscience/metaphlan{major_version}:{version}'
DEFAULT_VERSION = '4.0.6'
DEFAULT_WORKERS = 5
DEFAULT_REGION = 'GRA11'
DEFAULT_PROVIDER = 'ovh'
DEFAULT_DEPTH=20000000
DEFAULT_SEED=42
DEFAULT_CHM13V2='https://genome-idx.s3.amazonaws.com/bt/chm13v2.0.zip'

MAX_RETRY_PHASE1 = 2
MAX_RETRY_PHASE2 = 5

def metaphlan4(scitq_server, batch, source_s3, output_s3, final_output_s3, metaphlan_s3,
        human_catalog, region=DEFAULT_REGION, workers=DEFAULT_WORKERS, metaphlan_version=DEFAULT_VERSION,
        provider=DEFAULT_PROVIDER, depth=DEFAULT_DEPTH, seed=DEFAULT_SEED):
    """Launch biomscope using scitq in two phase, final compilation is done locally.
    Requires awscli, awscli-plugin-endpoint, combine_csv, sed and cut. Paramaters are
    explained through commande line --help"""

    s=Server(scitq_server, style='object')

    # remove trailing slash
    source_s3 = source_s3.rstrip('/')
    output_s3 = output_s3.rstrip('/')
    
    if not (metaphlan_s3.endswith('.tar.gz') or metaphlan_s3.endswith('.tgz')):
        raise RuntimeError(f'metaphlan_s3 should be in the form s3://bucket/path.../whatever.tgz (or .tar.gz) and not {metaphlan_s3}')


    fastqs = [fastq.name for fastq in 
                list_content(source_s3) if fastq.name.endswith('fastq.gz')]
    
    # fastqs are supposed to be grouped in folders each folder representing a sample
    samples = {}
    for fastq in fastqs:
        sample = fastq.split('/')[-2]
        if sample not in samples:
            samples[sample]=[fastq]
        else:
            samples[sample].append(fastq)

    major_version = metaphlan_version.split('.')[0]
    version = '4.0.6.1' if metaphlan_version=='4.0.6' else metaphlan_version
    docker = DOCKER.format(version=version, major_version=major_version)

    if human_catalog.endswith('.zip'):
        human_catalog_action = 'unzip'
    elif human_catalog.endswith('.tgz') or human_catalog.endswith('.tar.gz') or human_catalog.endswith('.tar'):
        human_catalog_action = 'untar'
    else:
        raise RuntimeError(f'This extension is unsupported for human catalog: {human_catalog}')

    if major_version=='3':
        metaphlan_option=''
    else:
        metaphlan_option='--offline'

    tasks = []
    for sample,fastqs in samples.items():
        command=f"""sh -c 'fastp \
            --adapter_sequence AGATCGGAAGAGCACACGTCTGAACTCCAGTCA --adapter_sequence_r2 AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT \
            --cut_front --cut_tail --n_base_limit 0 --length_required 60 --in1 /input/*.1.fastq.gz --in2 /input/*.2.fastq.gz \
            --out1 /input/{sample}_fp.1.fastq --out2 /input/{sample}_fp.2.fastq 
            bowtie2 -p $CPU --mm -x /resource/chm13v2.0/chm13v2.0 -1 /input/{sample}_fp.1.fastq  \
                -2 /input/{sample}_fp.2.fastq | samtools fastq -@ 2 -f 12 -F 256 -1 /input/{sample}_noh.1.fastq \
                -2 /input/{sample}_noh.2.fastq -0 /dev/null -s /dev/null -N
            parallel seqtk sample -s{seed} /input/{sample}_noh.{{}}.fastq {depth} \\> /input/{sample}_norm.{{}}.fastq ::: 1 2
            cat /input/{sample}_norm.*.fastq |metaphlan --input_type fastq \
        --no_map {metaphlan_option} --bowtie2db /resource/metaphlan/bowtie2 \
        --nproc $CPU -o /output/{sample}.metaphlan4_profile.txt' """
        tasks.append(
            s.task_create(
                command=command,
                name=sample,
                batch=batch,
                input=' '.join(fastqs),
                output=f'{output_s3}/{sample}',
                resource=f'{metaphlan_s3}|untar {human_catalog}|{human_catalog_action}',
                container=docker
            )
        )
    if workers:
        s.worker_deploy(number=workers,
            batch=batch,
            region=region,
            provider=provider,
            flavor='c2-120' if provider=='ovh' else 'Standard_D32ads_v5',
            concurrency=4,
            prefetch=1)
    s.join(tasks, retry=MAX_RETRY_PHASE1)

    resource = None
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
        resource = f'{metaphlan_s3}|untar'
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
            resource=resource,
            command = command
        )
    
    if workers:
        s.worker_deploy(number=1,
            batch=batch+'_metaphlan4_p2',
            region=region,
            provider=provider,
            flavor='c2-30' if provider=='ovh' else 'Standard_D8ads_v5',
            concurrency=1,
            prefetch=1)

    s.join([task], retry=MAX_RETRY_PHASE2)

    sync(final_output_s3,batch)


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
    parser.add_argument('--provider', type=str, 
        help=f'Provider for instances (ovh or azure) - default to {DEFAULT_PROVIDER}', choices=['ovh','azure'], default=DEFAULT_PROVIDER)    
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS,
        help=f'how many workers should we have, default to {DEFAULT_WORKERS}. (setting to 0 will prevent recruitment)')
    parser.add_argument('--metaphlan-version', type=str, default='4.0.6',
        help=f'what version of metaphlan should be used (3.1.0, 4.0.3, 4.0.5 or 4.0.6)')
    parser.add_argument('--depth', type=int, default=DEFAULT_DEPTH,
        help=f'what should be the normalization depth (default to {DEFAULT_DEPTH} for each pair member)')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED,
        help=f'what should be the seed for normalization randomness (default to {DEFAULT_SEED})')
    parser.add_argument('--human-catalog', type=str, default=DEFAULT_CHM13V2,
        help=f'A tar gz file human catalog for chm13v2 (default to {DEFAULT_CHM13V2})')
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
        provider=args.provider,
        workers=args.workers,
        metaphlan_version=args.metaphlan_version,
        depth=args.depth,
        seed=args.seed
    )