# this script is just a helper for the process explained here:
# https://wiki.gmt.bio/doku.php?id=dataset:camisim

import csv
import pandas as pd
import os
from subprocess import run
from scitq.lib import Server
import argparse
import math

DEFAULT_BATCH = "my_camisim"
DEFAULT_REGION = "WAW1"
DEFAULT_WORKERS = 5
DEFAULT_SEED = 42
DEFAULT_CONCURRENCY = 9
DEFAULT_DEPTH = 20

SAMPLE_SUBDIR = 'samples'
CONFIG_INI = """[Main]
seed={seed}
max_processors={concurrency}
dataset_id={name}
output_directory=/output/
temp_directory=/tmp
gsa=False
pooled_gsa=False
anonymous=False
compress=1

[ReadSimulator]
readsim=tools/art_illumina-2.3.6/art_illumina
error_profiles=tools/art_illumina-2.3.6/profiles
samtools=tools/samtools-1.3/samtools
profile=hi150
size={size}
type=art
fragments_size_mean=350
fragment_size_standard_deviation=27

[CommunityDesign]
ncbi_taxdump=tools/ncbi-taxonomy_20170222.tar.gz
strain_simulation_template=scripts/StrainSimulationWrapper/sgEvolver/simulation_dir
number_of_samples=1
distribution_file_paths=/input/{composition_file}

[community0]
max_strains_per_otu=1
ratio=1
mode=differential
log_mu=1
log_sigma=2
gauss_mu=1
gauss_sigma=1
view=False
metadata=/input/{metadata_file}
id_to_genome_file=/input/{id_to_genome_file}
genomes_total={genomes}
genomes_real={genomes}
"""

DOCKER_IMAGE='cami/camisim:1.3.0'

def read_tsv(filename):
    with open(filename, 'r') as f:
        csv_file = csv.DictReader(f, dialect=csv.excel_tab)
        for line in csv_file:
            yield line

class CamisimHelper:
    """A small helper to prepare for CAMISIM simulation
    """

    def __init__(self, name, samples, genome_source, seed, s3_camisim_config_folder, 
            scitq_server, region, s3_camisim_output, workers, depth, job_threads=4):
        print('Initializing')
        self.name = name
        with open(samples,'r') as sample_file:
            self.samples = pd.read_csv(sample_file, sep='\t', index_col=0)
        self.genome_source = genome_source
        self.seed = seed
        self.job_threads = job_threads
        self.workers = workers
        self.depth = depth
        self.genomes = []
        if s3_camisim_config_folder.endswith('/'):
            s3_camisim_config_folder = s3_camisim_config_folder[:-1]
        self.s3_camisim_config_folder = s3_camisim_config_folder
        if s3_camisim_output.endswith('/'):
            s3_camisim_output=s3_camisim_output[:-1]
        self.s3_camisim_output = s3_camisim_output
        
        self.s = Server(scitq_server)
        self.region = region
        self.run()


    def make_files(self):
        print('Building files')
        os.mkdir(SAMPLE_SUBDIR)
        for sample in self.samples.columns:
            sample_dir = os.path.join(SAMPLE_SUBDIR, sample)
            if not os.path.isdir(sample_dir):
                os.mkdir(sample_dir)
            composition = self.samples[sample]
            composition = composition[composition!=0.0]
            composition = composition/composition.sum()
            composition.to_csv(f'{sample_dir}/composition.tsv', header=False, sep='\t')
            with open(f'{sample_dir}/id_to_genome.tsv','w') as f:
                for specie in composition.index:
                    if specie not in self.genomes:
                        self.genomes.append(specie)
                    f.write(f'{specie}\t{os.path.join("/resource/genomes", specie)}.fa\n')
            with open(f'{sample_dir}/metadata.tsv','w') as f:
                f.write('genome_ID\tOTU\tNCBI_ID\tnovelty_category\n')
                for i,specie in enumerate(composition.index):
                    f.write(f'{specie}\tOTU_{i+1}\t22\tknown strain\n')
            with open(f'{sample_dir}/config.ini','w') as f:
                f.write(CONFIG_INI.format(
                    seed=self.seed,
                    concurrency=self.job_threads,
                    name=sample,
                    composition_file='composition.tsv',
                    metadata_file='metadata.tsv',
                    id_to_genome_file='id_to_genome.tsv',
                    genomes=len(composition),
                    # size in GB equal depth * 10^3 * 150 (read size) / 10^9, i.e. detph * 0.15
                    size = math.ceil( self.depth * 0.15 )
                ))
            
    def push_to_s3(self):
        print('Pushing to s3')
        run(f'aws s3 sync {SAMPLE_SUBDIR} {self.s3_camisim_config_folder}',
            shell=True, check=True)
    
    def create_tasks(self):
        print('Launching tasks')
        self.tasks = []
        for sample in self.samples.columns:
            self.tasks.append(
                self.s.task_create(
                    command=f"-c 'python3 metagenomesimulation.py /input/config.ini > /dev/null'",
                    container_options="--entrypoint sh",
                    name=sample,
                    batch=self.name,
                    input=f"{self.s3_camisim_config_folder}/{sample}/",
                    resource=f"{self.genome_source}|untar",
                    output=f'{self.s3_camisim_output}/{sample}/',
                    container=DOCKER_IMAGE
                )
            )
    
    def launch(self):
        self.s.worker_deploy(region=self.region, flavor="i1-180", 
            number=self.workers, batch=self.name,
            concurrency=DEFAULT_CONCURRENCY)
        self.s.join(self.tasks, retry=2)

    def run(self):
        self.make_files()
        self.push_to_s3()
        self.create_tasks()
        self.launch()


if __name__=='__main__':
    SCITQ_SERVER = os.environ.get('SCITQ_SERVER')
    parser = argparse.ArgumentParser(
                    prog = 'SCITQ Camisim',
                    description = 'Launch a Camisim simulation using specific genomes')
    parser.add_argument('tsv_abundance', type=str, 
        help='TSV abundance file where each column is a sample and each line a specie')
    parser.add_argument('s3_genomes_archive', type=str, 
        help="""a tar.gz archive containing all the genomes - they must untar in a genomes folder
        and they must match the TSV abundance line name followed by .fa.
        For instance if the TSV abundance file has a line begining with specie001 then the archive should contain 'genomes/specie001.fa' file""")
    parser.add_argument('s3_camisim_config_folder', type=str, 
        help='a temporary S3 folder where CAMISIM configuration files will be copied')
    parser.add_argument('s3_camisim_output', type=str, 
        help='the result S3 folder where CAMISIM output will be copied')
    
    

    parser.add_argument('--depth', type=int, 
        help=f'CAMISIM simulation depth in million of pair of reads, default to {DEFAULT_DEPTH}', default=DEFAULT_DEPTH)
    parser.add_argument('--seed', type=int, 
        help=f'SCITQ server FQDN, default to {DEFAULT_SEED}', default=DEFAULT_SEED)


    parser.add_argument('--scitq', type=str, 
        help=f'SCITQ server FQDN, default to {SCITQ_SERVER}', default=SCITQ_SERVER)
    parser.add_argument('--batch', type=str, 
        help=f'SCITQ batch name, default to "{DEFAULT_BATCH}"', default=DEFAULT_BATCH)
    parser.add_argument('--region', type=str, 
        help=f'Provider region - default to {DEFAULT_REGION} - Warsow at OVH', default=DEFAULT_REGION)
    parser.add_argument('--workers', type=int, 
        help=f'Number of instances to use, default to {DEFAULT_WORKERS} (each worker will take up to 72h)', default=DEFAULT_WORKERS)
    args = parser.parse_args()

    if not args.scitq:
        raise RuntimeError('You must define which SCITQ server we use, either defining SCITQ_SERVER environment variable or using --scitq')


    CamisimHelper(
                name=args.batch,
                samples=args.tsv_abundance,
                genome_source=args.s3_genomes_archive,
                seed=args.seed,
                s3_camisim_config_folder=args.s3_camisim_config_folder,
                scitq_server=args.scitq,
                region=args.region,
                s3_camisim_output=args.s3_camisim_output,
                workers=args.workers,
                depth=args.depth)
