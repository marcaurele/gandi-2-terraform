# Generate Terraform file from Gandi DNS records

[![Pypi version](https://img.shields.io/pypi/v/gandi-2-terraform?color=blue)](https://pypi.org/project/gandi-2-terraform/)
[![Python versions](https://img.shields.io/pypi/pyversions/gandi-2-terraform.svg)](https://pypi.org/project/gandi-2-terraform/)
[![Build status](https://github.com/marcaurele/gandi-2-terraform/workflows/Build%20status/badge.svg)](https://github.com/marcaurele/gandi-2-terraform/actions)

> [!IMPORTANT]
> This repository has been archived as I moved all my domains out of Gandi.net and will not use their services anymore. Therefore I will not be able to keep updating the code if their API changes.

> [!WARNING]
> This project is archived on pypi.org too and will not receive any further update. The final version is `1.3.3`.

This tool aims to simplify managing DNS recods using Terrafom by making the initial import through a single operation.
It fetches DNS records from one or multiple domains you own with [Gandi.net](https://gandi.et) and generates TF files with the corresponding records' resources using `gandi_livedns_record` and defining each record in a set (see the example output). It will output all the `terraform import` command to execute for the records.

## Install

```console
$ pip install gandi-2-terraform
$ gandi2tf --help
```

### Usage

You need to provide the Gandi API key as an environment variable `GANDI_KEY` (same as for the TF provider).

```console
$ export GANDI_KEY=A1b2C3d4E5f6
```

When no argument is given, it will fetch all available domains for the given API key:

```console
$ gandi-2tf
```

Or it can generate the tf configuration file for a single domain:

```console
$ gandi-2tf example.com
```

Fetching the domains only owned by a single organization:

```console
$ gandi-2tf --organization-id 04303337-a1b0-4b96-8bd7-992005a072e9
```

### Options

* `--organization-id`: in case your API key has access to multiple organization, you can filter the list of domains fetched by a single organization ID (_uuid_).
* `--subdir`: flag to create a sub directory per domain and generate the `main.tf` inside it with a second file containing all the `import` commands.

## Configuration

In order to access the DNS records through the API, you have to provide your API key. It uses the same variable name than the [Gandi Terraform](https://registry.terraform.io/providers/go-gandi/gandi/latest) provider `GANDI_KEY`. See [Gandi authentication documentation](https://api.gandi.net/docs/authentication/) of their API on how to generate one.

## Example

```console
$ export GANDI_KEY=A1b2C3d4E5f6
$ gandi-2tf example.com
```

will generate a file `example.com.tf` containing:

```hcl
locals {
  example_com_records = {
    apex_a = {
      name = "@"
      type = "A"
      ttl  = 10800
      values = [
        "192.30.252.153",
        "192.30.252.154",
      ]
    }
    apex_mx = {
      name = "@"
      type = "MX"
      ttl  = 10800
      values = [
        "10 spool.mail.gandi.net.",
        "50 fb.mail.gandi.net.",
      ]
    }
    apex_txt = {
      name = "@"
      type = "TXT"
      ttl  = 10800
      values = [
        "\"v=spf1 include:_mailcust.gandi.net -all\"",
      ]
    }
    imap_cname = {
      name = "imap"
      type = "CNAME"
      ttl  = 10800
      values = [
        "access.mail.gandi.net.",
      ]
    }
    smtp_cname = {
      name = "smtp"
      type = "CNAME"
      ttl  = 10800
      values = [
        "relay.mail.gandi.net.",
      ]
    }
    webmail_cname = {
      name = "webmail"
      type = "CNAME"
      ttl  = 10800
      values = [
        "webmail.gandi.net.",
      ]
    }
  }
}

resource "gandi_livedns_record" "example_com" {
  for_each = local.example_com_records

  zone = "example.com"

  name   = each.value.name
  ttl    = each.value.ttl
  type   = each.value.type
  values = each.value.values
}
```
