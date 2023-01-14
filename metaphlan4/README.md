# Metaphlan4

Metaphlan4 is a state-of-the-art public pipeline estimating relative species abundances from human gut WGS samples ([MetaPhlAn](https://github.com/biobakery/MetaPhlAn)).

## Resource

You must download Metaphlan4 resource, `metaphlan4.tgz` (or see in gmtscience/metaphlan4 docker doc how to create it):

Metaphan resource: https://zenodo.org/record/7537081#.Y8LBN6fP1Bs

You must also push it to your S3 bucket (in below example, to `s3://bucket/resource/metaphlan4.tgz`)

## Performance

Analysis take ~16 minutes per sample. Given that concurrency is 4 per worker, this makes each worker do ~15 analysis/hour.
(estimated with a complex dataset of 200 samples (created with CAMISIM) at 2x10M reads of 150pb)

## Usage

A typical usage would be:

```bash
python scitq_metaphlan4.py mybatch s3://bucket/mybatch/fastqs s3://bucket/mybatch/temp s3://bucket/mybatch/results s3://bucket/resource/metaphlan4.tgz
```
