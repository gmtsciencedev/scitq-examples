# Metaphlan4

Metaphlan4 is a state-of-the-art public pipeline estimating relative species abundances from human gut WGS samples ([MetaPhlAn](https://github.com/biobakery/MetaPhlAn)).

## New: adapted for new providers

Recent versions of scitq support Microsoft Azure in addition to OVH, as well as Azure storage in addition to S3 storage. Microsoft Azure for instances requires the specific `--provider azure` option when launching the script. All `s3://...` URI may be replaced by `azure://...` URI (the standard way of specifying an Azure path is `https://<storageaccount>.blob.core.windows.net/<container>`, which translates in the scitq form as `azure://<container>`, see [scitq documentation](https://scitq.readthedocs.io/en/latest/usage/#input-i) for details). 

When using Azure as a provider for instances, choose the following options:

- `--region swedencentral` (also any region will do as long as it is a real Azure region like `northeurope` or `westeurope`)

## Resource

You must download Metaphlan4 resource, `metaphlan4.tgz` (or see in gmtscience/metaphlan4 docker doc how to create it):

Metaphan resource: https://zenodo.org/record/7537081#.Y8LBN6fP1Bs

You must also push it to your S3 bucket (in below example, to `s3://bucket/resource/metaphlan4.tgz`) (which can be done by `scitq-fetch copy metaphlan4.tgz s3://bucket/resource/`).

## Performance

Analysis take ~16 minutes per sample. Given that concurrency is 4 per worker, this makes each worker do ~15 analysis/hour.
(estimated with a complex dataset of 200 samples (created with CAMISIM) at 2x10M reads of 150pb)

## Usage

A typical usage would be:

```bash
python scitq_metaphlan4.py mybatch s3://bucket/mybatch/fastqs s3://bucket/mybatch/temp s3://bucket/mybatch/results s3://bucket/resource/metaphlan4.tgz
```

## With filter

A specific version of the script, `scitq_metaphlan4_filter.py` is now proposed that include fastp filtering, removal of human genome and normalization of sample by seqtk. Only MetaPhlAn 4.0.6 is supported with this version right now.