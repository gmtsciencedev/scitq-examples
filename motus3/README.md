# mOTUs 3

mOTUs 3 is a state-of-the-art public generalist pipeline (e.g. not dedicated to gut like Metaphlan) estimating relative species abundances from WGS samples ([mOTUs](https://motu-tool.org/index.html)).

## Resource

You must download Metaphlan4 resource, `motus.tgz` (or see in gmtscience/motus docker doc how to create it):

motus 3.0.3 resource: https://zenodo.org/record/7537507#.Y8L7dqfP1Bt

You must also push it to your S3 bucket (in below example, to `s3://bucket/resource/motus.tgz`)

## Performance

Analysis take ~16 minutes per sample. Given that concurrency is 4 per worker, this makes each worker do ~15 analysis/hour.
(estimated with a complex dataset of 200 samples (created with CAMISIM) at 2x10M reads of 150pb)

## Usage

A typical usage would be:

```bash
python scitq_motus.py mybatch s3://bucket/mybatch/fastqs s3://bucket/mybatch/results s3://bucket/resource/motus.tgz
```
