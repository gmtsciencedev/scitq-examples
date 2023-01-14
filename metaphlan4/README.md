# Metaphlan4

Metaphlan4 is a state-of-the-art public pipeline estimating relative species abundances from WGS samples ([MetaPhlAn](https://github.com/biobakery/MetaPhlAn)).

## Resource



## Performance

Analysis take ~16 minutes per sample. Given that concurrency is 4 per worker, this makes each worker do ~15 analysis/hour.
(estimated with a complex dataset of 200 samples (created with CAMISIM) at 2x10M reads of 150pb)


