import subprocess as sp
from scitq.lib import Server
import argparse
from scitq.fetch import list_content, sync
import os

def kraken2(scitq_server, s3_input, s3_output, s3_kraken_database,
        bracken=False, download=False, fastq=False,
        batch='my_kraken2', region='WAW1', workers=5, database='',
        flavor='i1-180', provider='ovh', only_bracken=False,
        concurrency=1):
    """Launch a kraken2 scan on FASTA files in s3_input folder using database present
    in s3_kraken_database, and putting result in s3_output folder.

    - scitq_server: FQDN of SCITQ server (no port, no http, just the server name)
    - s3_input: an S3 path to a folder containing FASTA file (s3://bucket/path/)
    - s3_output: an S3 path to an output S3 folder (and may be empty - hence non existing)
    - s3_kraken_database: an S3 path to an tar gziped archive that contain kraken2 db
    - batch: an optional name for SCITQ batch (default to my_kraken2)
    - region: an OVH region for the instances. Default to Warsow (WAW1)
    - workers: the number of workers (default to 5)
    - concurrency: the number of process per worker (default to 1)

    """
    if not (s3_kraken_database.endswith('.tgz') or s3_kraken_database.endswith('.tar.gz')):
        raise RuntimeError(f'Please use a tar gziped archive as s3_kraken_database')
    s3_db_path = f"{s3_kraken_database}|untar"


    s=Server(scitq_server)

    
    
    if only_bracken:
        sample_extension='.report'
    elif fastq:
        sample_extension='.fastq.gz'
    else:
        sample_extension='.fa'

    samples = {}
    for item in [item.name for item in list_content(s3_input) 
                    if item.name.endswith(sample_extension)]:
        if fastq:
            sample = item.split('/')[-2]
        else:
            sample,_ = os.path.splitext(os.path.split(item)[-1])
        if sample not in samples:
            samples[sample]=[item]
        else:
            samples[sample].append(item)
            
    if len(samples)==0:
        raise RuntimeError(f'No {"gzipped FASTQ (.fastq.gz)" if fastq else "KRAKEN2 report (.report)" if only_bracken else "FASTA (.fa)"} samples found in {s3_input}...')

    if not s3_output.endswith('/'):
        s3_output+='/'

    tasks = []
    for name,sequences in samples.items():
        print(f'Launching for {name} {sequences}')
        if fastq:
            input='--paired --gzip-compressed /input/*.fastq.gz'
        else:
            input='/input/*.fa'
        if only_bracken:
            command=f"sh -c 'cd /output/ && \
    bracken -d /resource/ -i /input/{name}.report -o /output/{name}.bracken -w /output/{name}-bracken.report'"
        elif bracken:
            command=f"sh -c 'cd /output/ && \
    kraken2 --use-names --threads $CPU --db /resource/{database} --report /output/{name}.report \
        {input} > /output/{name}.kraken && \
    bracken -d /resource/{database} -i /output/{name}.report -o /output/{name}.bracken -w /output/{name}-bracken.report'"
        else:
            command=f"sh -c 'cd /output/ && kraken2 --use-names --threads $CPU --db /resource/{database} --report /output/{name}.report \
    {input} > /output/{name}.kraken'"
        tasks.append(s.task_create(command=command,
                input=' '.join(sequences),
                output=s3_output+name,
                resource=s3_db_path,
                container="gmtscience/kraken2bracken",
                batch=batch,
                ))

    if flavor.lower()!='none' and workers>0:
        s.worker_deploy(region=region, flavor=flavor, number=workers, batch=batch,
            concurrency=concurrency, prefetch=concurrency, provider=provider)

    if flavor.lower()!='none' or download:
        s.join(tasks, retry=2)

    if download:
        sync(s3_output, batch)


if __name__=='__main__':
    SCITQ_SERVER = os.environ.get('SCITQ_SERVER')
    parser = argparse.ArgumentParser(
                    prog = 'SCITQ Kraken2',
                    description = 'Launch a Kraken2 scan on some FASTA files')
    parser.add_argument('s3_input', type=str, help='S3 folder for FASTA files')
    parser.add_argument('s3_kraken', type=str, help='S3 path to Kraken DB')
    parser.add_argument('s3_output', type=str, help='S3 folder for results')
    
    parser.add_argument('--bracken', action='store_true', 
        help=f'Add bracken analysis to kraken2 to enhance species estimation.')
    parser.add_argument('--fastq', action='store_true', 
        help=f'Uses sample paired .fastq.gz sequences (grouped in a sample dir) instead of genome .fa files')
    parser.add_argument('--download', action='store_true', 
        help=f'Download results in the end.')
    parser.add_argument('--scitq', type=str, 
        help=f'SCITQ server FQDN, default to {SCITQ_SERVER}', default=SCITQ_SERVER)
    parser.add_argument('--batch', type=str, 
        help=f'SCITQ batch name, default to "my_kraken2"', default="my_kraken2")
    parser.add_argument('--region', type=str, 
        help=f'Provider region - default to WAW1 - Warsow at OVH', default="WAW1")
    parser.add_argument('--workers', type=int, 
        help=f'Number of instances to use, default to 5 (each worker will treat ~2 1MB-long FASTA per hour)', default=5)
    parser.add_argument('--concurrency', type=int, 
        help=f"The number of process per worker, default to 1", default=1)
    parser.add_argument('--database', type=str, default='',
        help=f'If kraken database tar contains a subdirectory specify it here')
    parser.add_argument('--flavor', type=str, default='i1-180',
        help=f'Chose an alternate flavor of instance (i1-180 is fine for GTDB base\
 which requires loads of mem, but smaller db like mgnify might accomodate with a\
 c2-120, if flavor is none, then there will be no instance automatically allocated)')
    parser.add_argument('--provider', type=str, choices=['ovh','azure'], default='ovh',
        help="Choose the provider, default to ovh, can be azure also")
    parser.add_argument('--only-bracken', action="store_true",
        help=f'This option is for running only bracken when you have already run kraken2 - the input should contain .report files in this case')
    args = parser.parse_args()

    if not args.scitq:
        raise RuntimeError('You must define which SCITQ server we use, either defining SCITQ_SERVER environment variable or using --scitq')

    kraken2(args.scitq, args.s3_input, args.s3_output, args.s3_kraken, batch=args.batch,
        region=args.region, workers=args.workers, bracken=args.bracken, download=args.download,
        fastq=args.fastq, database=args.database, flavor=args.flavor, only_bracken=args.only_bracken,
        provider=args.provider, concurrency=args.concurrency)
    
    
