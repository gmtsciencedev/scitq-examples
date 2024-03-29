from scitq.lib import Server
from scitq.fetch import list_content, sync
import subprocess
import argparse
import os


# Do not change that unless you know what you do
DOCKER = 'gmtscience/motus'
DEFAULT_WORKERS = 5
DEFAULT_REGION = 'GRA11'
DEFAULT_PROVIDER = 'ovh'

MAX_RETRY_PHASE1 = 2
MAX_RETRY_PHASE2 = 5

def motus(scitq_server, batch, source_s3, output_s3, motus_s3,
        region=DEFAULT_REGION, workers=DEFAULT_WORKERS, download=False,
        provider=DEFAULT_PROVIDER):
    """Launch biomscope using scitq in two phase, final compilation is done locally.
    Requires awscli, awscli-plugin-endpoint, combine_csv, sed and cut. Paramaters are
    explained through commande line --help"""

    s=Server(scitq_server, style='object')

    # remove trailing slash
    source_s3 = source_s3.rstrip('/')
    output_s3 = output_s3.rstrip('/')
    
    if not (motus_s3.endswith('.tar.gz') or motus_s3.endswith('.tgz')):
        raise RuntimeError(f'motus_s3 should be in the form s3://bucket/path.../whatever.tgz (or .tar.gz) and not {motus_s3}')


    fastqs = [fastq.name for fastq in 
                list_content(source_s3) if fastq.name.endswith('fastq.gz')]
    

    if len(fastqs)==0:
        raise RuntimeError(f'Source ({source_s3}) does not seems to contain any .fastq.gz files')

    # fastqs are supposed to be grouped in folders each folder representing a sample
    samples = {}
    for fastq in fastqs:
        sample = fastq.split('/')[-2]
        if sample not in samples:
            samples[sample]=[fastq]
        else:
            samples[sample].append(fastq)





    tasks = []
    for sample,inputs in samples.items():
        fastqs=[os.path.split(input)[1] for input in inputs]
        if len(fastqs)!=2:
            raise RuntimeError(f'Sample should only contains pair of samples: {sample} contains {fastqs}')
        tasks.append(
            s.task_create(
                command=f"""sh -c 'motus profile -db /resource/db_mOTU -f /input/{fastqs[0]} -r /input/{fastqs[1]} -n {sample} -o /output/{sample}.motus -t $CPU' """,
                name=sample,
                batch=batch,
                input=' '.join(inputs),
                output=f'{output_s3}/{sample}',
                resource=f'{motus_s3}|untar',
                container=DOCKER
            )
        )


    if workers:
        s.worker_deploy(number=workers,
            batch=batch,
            region=region,
            flavor='c2-120' if provider=='ovh' else 'Standard_D32ads_v5',
            concurrency=8,
            prefetch=2)
    s.join(tasks, retry=MAX_RETRY_PHASE1)

    if download:
        sync(output_s3, batch)


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
    parser.add_argument('motus_s3', type=str, 
        help='An S3 file path for motus databases, motus.tgz, which can be downloaded from Zenodo: https://zenodo.org/record/7537507#.Y8MWTuLMKJG')

    parser.add_argument('--scitq', type=str, 
        help=f'SCITQ server FQDN, default to {SCITQ_SERVER}', default=SCITQ_SERVER)
    parser.add_argument('--region', type=str, 
        help=f'Provider region - default to {DEFAULT_REGION}', default=DEFAULT_REGION)
    parser.add_argument('--provider', type=str, choices=['ovh','azure'], default=DEFAULT_PROVIDER,
        help=f"Cloud provider for instances, default to {DEFAULT_PROVIDER} ")
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS,
        help=f'how many workers should we have, default to {DEFAULT_WORKERS}.')
    parser.add_argument('--download', action='store_true', 
        help=f'Download locally at the end.')
    
    args = parser.parse_args()

    if not args.scitq:
        raise RuntimeError('You must define which SCITQ server we use, either defining SCITQ_SERVER environment variable or using --scitq')


    motus(
        batch=args.batch,
        scitq_server=args.scitq,

        source_s3=args.source_s3,
        output_s3=args.output_s3,
        motus_s3=args.motus_s3,

        region=args.region,
        provider=args.provider,
        workers=args.workers,
        download=args.download
    )