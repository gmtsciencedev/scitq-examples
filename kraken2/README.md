# kraken2

Kraken2 is really usefull to quickly align sample reads or whole genomes against huge databases. When using large database be aware of a relative high number of false positives. 

## resources

This example requires:

- FASTA genomes in an S3 folder,
- A Kraken2 database archived with `tar cvzf krakendb.tgz .` in the folder containing Kraken2 database individual files. We will detail how to proceed with GTDB r207 excellent database just below (unfortunately the resulting file is big, more than 220GB, so we cannot provide it, sorry).

### Prepare GTDB r207 Kraken2 database

This requires ~600GB of temporary free space of drive and downloading will take several hours (consider doing it in a screen/tmux session on a remote server)

```bash
mkdir gtdb_kraken
cd gtdb_kraken
ncftpget ftp://ftp.tue.mpg.de/ebio/projects/struo2/GTDB_release207/kraken2/database150mers.kraken
ncftpget ftp://ftp.tue.mpg.de/ebio/projects/struo2/GTDB_release207/kraken2/hash.k2d
ncftpget ftp://ftp.tue.mpg.de/ebio/projects/struo2/GTDB_release207/kraken2/opts.k2d
ncftpget ftp://ftp.tue.mpg.de/ebio/projects/struo2/GTDB_release207/kraken2/seqid2taxid.map
ncftpget ftp://ftp.tue.mpg.de/ebio/projects/struo2/GTDB_release207/kraken2/taxo.k2d
tar cvzf ../kraken_db.tgz .
cd ..
rm -fr gtdb_kraken
aws s3 cp kraken_db.tgz s3://mybucket/resource/kraken_db.tgz
```

### Prepare some FASTA files in an S3 folder

Files must end in `.fa` and be standard genomic FASTA. 

## run the script

```bash
python scitq_kraken2.py s3://mybucket/input/fasta/ s3://mybucket/resource/kraken_db.tgz s3://mybucket/output/kraken2/
```

Look at `python scitq_kraken2.py -h` to get more options (like specifying region, number of workers or so)

NB: If SCITQ version is below v1.0rc6, and you use a specific S3 endpoint, it must be exported to AWS_ENDPOINT_URL shell environment variable before running the script.

## troubleshooting

This script requires large amount of memory (with GTDB full database) and use OVH special instance i1-180. This instance is sometime hard to find (and may turn to error upon deploy). This error is due to some limitations within OVH system and is not related to SCITQ (or Kraken2 of course). It is advised to look at OVH console to see if instance are sane (any worker that turns with a blue dot in SCITQ UI is fine, only workers that stay with a grey dot for a long time are likely to have failed). You can add manually via SCITQ UI more instances if some fails (just delete the failed ones with SCITQ UI):

- concurrency: 1
- prefetch: 1
- flavor: i1-180
- region: any region (GRA11 or UK1 or WAW1 or BHS5 or GRA7 should be fine)
- batch: the name of your batch (my_kraken2 if you kept the default)
number: stay below 5 here

In case of trouble, call OVH support to know in which region you're likely to find some i1-180 instances.