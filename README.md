# Generate Terraform file from Gandi DNS records

[![Pypi version](https://img.shields.io/pypi/v/gandi-2-terraform?color=blue)](https://pypi.org/project/gandi-2-terraform/)
[![Python versions](https://img.shields.io/pypi/pyversions/gandi-2-terraform.svg)](https://pypi.org/project/gandi-2-terraform/)
[![Build status](https://github.com/marcaurele/gandi-2-terraform/workflows/Build%20status/badge.svg)](https://github.com/marcaurele/gandi-2-terraform/actions)


This tool aims to simplify managin DNS recods using Terrafom by making the initial import through a single operation.
It fetches DNS records from one or multiple domains you own with [Gandi.net](https://gandi.et) and generates TF files with the corresponding records' resources using `gandi_livedns_record` and defining each record in a set (see the example output).

## Install

```console
$ pip install gandi-2-terraform
$ gandi2tf --help
```

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
