# SCITQ examples

These examples are designed to be used with [scitq](https://github.com/gmtsciencedev/scitq). Please read [scitq documentation](https://scitq.readthedocs.io/en/latest/) before trying them.

For this serie of examples you must have installed scitq, and not only `pip install scitq` but a complete install:

- it must be linked to your provider. These examples use OVH as a provider and will refer to OVH instances (which are described here: https://www.ovhcloud.com/en/public-cloud/prices/).
- it must be linked to an S3 provider (and here we also use OVH S3)


For some of the examples, you will need to create some resources which means to have access to some Unix server with some disk space and network bandwidth.

## S3 path

Most of the time these commands will take input or output as S3 path :
`s3://bucket/path/to/file.fa`

Sometime you will need direct access to those folder (thus having a proper `.aws` folder with `credentials` and optional `config`)

In the specific case of OVH S3, you will need the following `.aws/config` (this is documented in OVH : https://docs.ovh.com/gb/en/storage/object-storage/pcs/getting-started-with-the-swift-s3-api/#configure-aws-client):

```ini
[plugins]
endpoint = awscli_plugin_endpoint

[profile default]
region = gra
s3 =
  endpoint_url = https://s3.gra.perf.cloud.ovh.net
  signature_version = s3v4
s3api =
  endpoint_url = https://s3.gra.perf.cloud.ovh.net
```
!!! note
    be careful to adapt endpoint_url to the OVH region of your S3 storage, the above example is only for GRA region (Graveline).

So to use the examples, you will need to create a bucket and load it with some files that will be explained for each example. This is done the usual way with `aws s3 cp ...` or `aws s3 sync ...` but it can also be done with `scitq-fetch copy ...` or `scitq-fetch sync ...`.

In the case of python, it is advised to use `scitq.fetch` library over native tools, it provides high level provider-agnostic functions such as `scitq.fetch.sync` or `scitq.fetch.list_content` which are simpler to use and provide flexibility.

## New: Azure storage and instances

### Azure storage
S3 storage may now be optionnally replaced by Azure storage. The configuration steps are described in [scitq documentation](https://scitq.readthedocs.io/en/latest/specific/#azure-storage).

You can of course use Azure native tools to exchange with these storages, but `scitq-fetch copy ...` or `scitq-fetch sync ...` will work transparently (that is use the same syntax wether the storage is S3 or Azure). In scitq, Azure path designations are simplified: the standard way of specifying an Azure path is `https://<storageaccount>.blob.core.windows.net/<container>`, which translates in the scitq form as `azure://<container>`, see [scitq documentation](https://scitq.readthedocs.io/en/latest/usage/#input-i) for details.

### Azure provider for instance
Note that using Azure as an instance provider is a completely independant option from the storage option (i.e. you can use an Azure storage with OVH as the instance provider, or use S3 storage with Azure as the instance provider). 

See [scitq documentation](https://scitq.readthedocs.io/en/latest/specific/#azure) to learn how to register Azure.

You will find some comment in the README.md of each tool as to the options that must be changed when using Azure.

## Independance from providers

These examples use OVH or Azure as providers for instances and storage. Although we are grateful to OVH and to Azure to have accepted us in their startup program, scitq is a free software independant of either. 

In all scripts, setting the option `--workers 0` will disable any automatic lifecycle option on any provider. You will have then the possibility to recruit manually your workers which is covered [here](https://scitq.readthedocs.io/en/latest/install/#manual-worker-deployment), using scitq UI to include them in the analysis batches that the scripts will create for you.

It is also possible not to use S3 or Azure storage. S3 is almost a de facto standard nowadays, and there are opensource solutions to deploy S3 (like [MinIO](https://min.io/)). You may also replace S3/Azure by standard NFS, but that will require a little adaptation of the scripts.

Last, scitq is just a way to ease docker use on a set of workers, you could also achieve much of what it does using plain docker and GNU parallel. The dockers we use are public and you can grab them on [Docker hub](https://hub.docker.com/search?q=gmtscience) directly, except for CAMISIM docker, which is public but maintained directly by CAMISIM team (many thanks to them): [cami/camisim:1.3.0](https://hub.docker.com/r/cami/camisim).

Last, as you may be aware, it is difficult to translate the reference and meaning of cloud providers, so we have listed the type of instance (called flavor in scitq, taken after Openstack wording) commonly used in the script, the OVH word for it, the Azure word for it, and its description.

OVH flavor | Azure flavor | Description
--|--|--
c2-30 | Standard_D8ads_v5 | 8 vcpu / 30 gb instance used for some basic computation 
c2-120 | Standard_D32ads_v5 | 32 vcpu / 120 gb instance used for larger computation (can run 4 metaphlan/motus in a parallel way)
i1-180 |  Standard_E32bds_v5 | 32 vcpu / +180 gb instance with high IOPS, typically used for CAMISIM which is strongly dependant on disk IO (read/write access). 
~i1-180 (*) | Standard_E64-32ads_v5 | 32+ vcpu / 512 gb instance required for Kraken2+GTDB which need high memory (Kraken2+MGNIFY needs a lot less)

(*) there are no perfectly suited instances in OVH, we use i1-180 on which some swap space is activated (this is automatic with scitq) on the included high speed (NVMe) disks of this instance. As the disks are really quick this makes up for the low memory of the instance.