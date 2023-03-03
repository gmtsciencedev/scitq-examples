import subprocess as sp
from scitq.lib import Server
import argparse
from scitq.fetch import get_s3
import os

def kraken2(scitq_server, s3_input, s3_output, s3_kraken_database,
        bracken=False, download=False, fastq=False,
        batch='my_kraken2', region='WAW1', workers=5, database=''):
    """Launch a kraken2 scan on FASTA files in s3_input folder using database present
    in s3_kraken_database, and putting result in s3_output folder.

    - scitq_server: FQDN of SCITQ server (no port, no http, just the server name)
    - s3_input: an S3 path to a folder containing FASTA file (s3://bucket/path/)
    - s3_output: an S3 path to an output S3 folder (and may be empty - hence non existing)
    - s3_kraken_database: an S3 path to an tar gziped archive that contain kraken2 db
    - batch: an optional name for SCITQ batch (default to my_kraken2)
    - region: an OVH region for the instances. Default to Warsow (WAW1)
    - workers: the number of workers (default to 5)

    """
    if not (s3_kraken_database.endswith('.tgz') or s3_kraken_database.endswith('.tar.gz')):
        raise RuntimeError(f'Please use a tar gziped archive as s3_kraken_database')
    s3_db_path = f"{s3_kraken_database}|untar"

    s3_bucket = s3_input.split('/')[2]
    s3_path = '/'.join(s3_input.split('/')[3:])

    s=Server(scitq_server)

    s3 = get_s3()
    bucket = s3.Bucket(s3_bucket)
    
    if fastq:
        sample_extension='.fastq.gz'
    else:
        sample_extension='.fa'

    samples = {}
    for item in [item.key for item in bucket.objects.filter(Prefix=s3_path) 
                    if item.key.endswith(sample_extension)]:
        if fastq:
            sample = item.split('/')[-2]
        else:
            sample,_ = os.path.splitext(os.path.split(item)[-1])
        path = f's3://{s3_bucket}/{item}'
        if sample not in samples:
            samples[sample]=[path]
        else:
            samples[sample].append(path)
            
    if len(samples)==0:
        raise RuntimeError(f'No {"gzipped FASTQ (.fastq.gz)" if fastq else "FASTA (.fa)"} samples found in {s3_input}...')

    if not s3_output.endswith('/'):
        s3_output+='/'

    tasks = []
    for name,sequences in samples.items():
        print(f'Launching for {name} {sequences}')
        if fastq:
            input='--paired --gzip-compressed /input/*.fastq.gz'
        else:
            input='/input/*.fa'
        if bracken:
            command=f"sh -c 'kraken2 --use-names --threads $CPU --db /resource/{database} --report /output/{name}.report \
    {input} > /output/{name}.kraken && \
    bracken -d /resource/ -i /output/{name}.report -o /output/{name}.bracken'"
        else:
            command=f"sh -c 'kraken2 --use-names --threads $CPU --db /resource/{database} --report /output/{name}.report \
    {input} > /output/{name}.kraken'"
        tasks.append(s.task_create(command=command,
                input=' '.join(sequences),
                output=s3_output+name,
                resource=s3_db_path,
                container="gmtscience/kraken2bracken",
                batch=batch,
                ))

    s.worker_deploy(region=region, flavor="i1-180", number=workers, batch=batch,
        concurrency=1, prefetch=1)
    s.join(tasks, retry=2)

    if download:
        sp.run([f'aws s3 sync {s3_output} {batch}'], shell=True, check=True)


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
    parser.add_argument('--database', type=str, default='',
        help=f'If kraken database tar contains a subdirectory specify it here')
    args = parser.parse_args()

    if not args.scitq:
        raise RuntimeError('You must define which SCITQ server we use, either defining SCITQ_SERVER environment variable or using --scitq')

    kraken2(args.scitq, args.s3_input, args.s3_output, args.s3_kraken, batch=args.batch,
        region=args.region, workers=args.workers, bracken=args.bracken, download=args.download,
        fastq=args.fastq, database=args.database)
    
    
