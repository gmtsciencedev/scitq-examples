# SCITQ examples

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

So to use the examples, you will need to create a bucket and load it with some files that will be explained for each example. This is done the usual way with `aws s3 cp ...` or `aws s3 sync ...` 

In the case of python, at the time of this writing, boto3 library makes life a little harder for non-AWS users, the endpoint_url present in `.aws/config` is not taken into account by boto3, scitq.fetch.get_s3() is recommanded over boto3.resource('s3') as it will read those values and connect to any S3 without additionnal options.
