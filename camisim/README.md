# CAMISIM

CAMISIM (https://github.com/CAMI-challenge/CAMISIM) is a reference program as regards sample simulators, and there are not many of them. It is a difficult program to use and is much challenging to distribute efficiently, as it consumes lots of resources in CPU, memory and one particularly delicate to tune: disk IO. Notably it makes a dramatically expensive use of temporary disk space with lots of read/write cycles. High IO instances (like OVH i1-180) are particularly adapted to CAMISIM.

Also CAMISIM is very slow due to all the extra files it prepares (notably SAM files converted to BAM files). By default with a depth of 2x10M reads (of 150bp), some sample may take up to 3 days to generate (if they are complex like rich natural samples, ~400 species). Average time is 12 hours (estimated on our latest batch of 200 samples).

That being said, the example is complete and will require minimal work from you, but you will have to pay for the simulation. Each day of i1-180 cost slightly less than 43 € (not including taxes). 1 days should give you 18 samples per i1-180 worker, which makes a sample ~2.50 € of computation (+ a few extra centimes for downloading and temporary storage, so let's call it 3 € / sample, provided you have enough of them).

Special thanks to Florian Plaza-Oñate for his help on CAMISIM setup.

## New: adapted for new providers

Recent versions of scitq support Microsoft Azure in addition to OVH, as well as Azure storage in addition to S3 storage. Microsoft Azure requires the specific `--provider azure` option when launching the script. All `s3://...` URI may be replaced by `azure://...` URI (the standard way of specifying an Azure path is `https://<storageaccount>.blob.core.windows.net/<container>`, which translates in the scitq form as `azure://<container>`, see [scitq documentation](https://scitq.readthedocs.io/en/latest/usage/#input-i) for details). 

## resources

CAMISIM resources are not very heavy and we have simplified things a lot (making lots of choices that fit our use of CAMISIM, see notably CONFIG_INI template within code and look into CAMISIM documentation for help). Roughly: we use only CAMISIM `metagenomesimulation.py` script which use external genomes that must be provided as a tar.gz archive (which composition is detailed just below), we generate 150bp long reads, 10 millions of pairs (but this figure of 10, called depth, can be changed with --depth parameter).

Here you will need two resources:
- a serie of input genomes in FASTA format,
- a TSV file describing each sample (relative) composition in the different genomes.

You will need to have your AWS access configured from where the script is run and awscli properly installed (the script will call `aws s3 ...` commands). Anyway you need that to send the genomes archive as explained below.

### genomes

Genomes should be named as you want but end in `.fa`. They should be put in a "genomes" folder and archived from the parent folder of genomes (so that the archive will create the populated genomes folder when extracted), and the resulting archive should be copied to a convenient S3 folder:

```bash
mkdir genomes
mv path/to/your/genome/*.fa genomes/
tar cvzf mygenomes.tar.gz genomes
scit-fetch copy mygenomes.tar.gz s3://mybucket/myfolder/
```
With that example, the second argument of the script will be `s3://mybucket/myfolder/mygenomes.tar.gz`

### samples.tsv

Now the TSV file should have samples in columns and genomes in lines: the genomes should be name after the file name (without the `.fa` extension). The samples can be named in any manner provided they translate sanely as file names (avoid space and special characters). Abundance in the different genomes should be positive floating numbers such as the sum for the sample (column sum) is strickly positive.

So for instance if we represent the content of the file with a table, and `mygenomes.tar.gz` contains `genomes/genome1.fa`, `genomes/genome2.fa` and `genomes/genome3.fa`:

| genomes | sample1 | sample2 | sample3 | sample4 |
| ------- | ------- | ------- | ------- | ------- | 
| genome1 |   0.1   |   0.2   |    0    |    0    |
| genome2 |   0.1   |    0    |   0.1   |    0    |
| genome3 |   0.1   |   0.2   |    0    |   100   |

NB: Columns are normalized by dividing all figures by the sum of the column.

TSV format is just one character line per line with column values separated by tabs (coined 'excel-tab' in python csv reader module).

For the next step, we call this file `samples.tsv`

### S3 result folders

You do not have to prepare that, they will be populated by the script. As you may know, S3 folders do not really exist, unless you put a file into them, so they don't even need to be created. Just be aware they will be created and consume some space in your S3.

One is a small folder that will receive CAMISIM individual sample files (that are prepared by the script from `samples.tsv`), let's call it `s3://mybucket/camisim/config`

The other will receive CAMISIM results, and this is big (figures easily rise to TeraBytes), mainly due to `.bam` files. You can delete those afterward if you do not need them (for instance if you care only for FASTQ files which are a lot leaner). Let's call it `s3://mybucket/camisim/results`.

## run the script

```bash
python scitq_camisim.py samples.tsv s3://mybucket/myfolder/mygenomes.tar.gz s3://mybucket/camisim/config s3://mybucket/camisim/results
```

Look at `python scitq_camisim.py -h` to get more options (like specifying depth, region, number of workers or so)

NB: If SCITQ version is below v1.0rc6, and you use a specific S3 endpoint, it must be exported to AWS_ENDPOINT_URL shell environment variable before running the script.

## troubleshooting

This script requires OVH special instance i1-180 (which is replaced by Standard_E32bds_v5 in Azure). The OVH instance is sometime hard to find (and may turn to error (red in scitq UI) upon deploy). This error is due to some limitations within OVH system and is not related to SCITQ (or CAMISIM of course).You can add manually via scitq UI more instances if some fails (just delete the failed ones with the UI):

The following choices are for OVH:

- concurrency: 9
- prefetch: 0
- flavor: i1-180 
- provider: ovh
- region: any region (GRA11 or UK1 or WAW1 or BHS5 or GRA7 should be fine)
- batch: the name of your batch (my_kraken2 if you kept the default)
number: stay below 5 here

For Azure:

- replace of course provider by: azure
- replace flavor with: Standard_E32bds_v5
- replace region with: swedencentral or northeurope (or whatever you want, these places tend to be cheaper at the time of this writing)
- otherwise keep the other choices.