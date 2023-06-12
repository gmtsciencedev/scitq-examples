# mOTUs 3

mOTUs 3 is a state-of-the-art public generalist pipeline (e.g. not dedicated to gut like Metaphlan) estimating relative species abundances from WGS samples ([mOTUs](https://motu-tool.org/index.html)).

## New: adapted for new providers

Recent versions of scitq support Microsoft Azure in addition to OVH, as well as Azure storage in addition to S3 storage. Microsoft Azure for instances requires the specific `--provider azure` option when launching the script. All `s3://...` URI may be replaced by `azure://...` URI (the standard way of specifying an Azure path is `https://<storageaccount>.blob.core.windows.net/<container>`, which translates in the scitq form as `azure://<container>`, see [scitq documentation](https://scitq.readthedocs.io/en/latest/usage/#input-i) for details). 

When using Azure as a provider for instances, choose the following options:

- `--region swedencentral` (also any region will do as long as it is a real Azure region like `northeurope` or `westeurope`)

## Resource

You must download Metaphlan4 resource, `motus.tgz` (or see in gmtscience/motus docker doc how to create it):

motus 3.0.3 resource: https://zenodo.org/record/7537507#.Y8L7dqfP1Bt

You must also push it to your S3 bucket (in below example, to `s3://bucket/resource/motus.tgz`) (which can be done by `scitq-fetch copy motus.tgz s3://bucket/resource/`).

## Performance

Analysis take ~30 minutes per sample (in 2x10M depth, 150bp). Given that concurrency is 8 per worker, this makes each worker do ~16 analysis/hour.
(estimated with a complex dataset of 200 samples created with CAMISIM)

## Usage

A typical usage would be:

```bash
python scitq_motus.py mybatch s3://bucket/mybatch/fastqs s3://bucket/mybatch/results s3://bucket/resource/motus.tgz
```
