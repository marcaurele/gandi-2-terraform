import os

import click

import requests


class Record:
    def __init__(self, name, r_type, ttl, value) -> None:
        self.name = name
        self.r_type = r_type
        self.ttl = ttl
        self.values = [value]


def fetch_records(domain):
    r = requests.get(
        f"https://dns.api.gandi.net/api/v5/domains/{domain}/records",
        headers={
            "X-Api-Key": os.getenv("GANDI_KEY"),
            "Accept": "text/plain",
        },
    )
    r.raise_for_status()
    return r.text


def fetch_domains_list(organization_id):
    payload = {"per_page": 1, "sort_by": "fqdn", "nameserver": "livedns"}
    if organization_id is not None:
        payload["sharing_id"] = organization_id

    # Get total count of domain to fetch them all in one request
    fake_head = requests.get(
        "https://api.gandi.net/v5/domain/domains",
        headers={"authorization": f'Apikey {os.getenv("GANDI_KEY")}'},
        params=payload,
    )
    fake_head.raise_for_status()

    try:
        total_count = int(fake_head.headers.get("total-count", 0))
    except ValueError:
        total_count = 0
    if total_count > 0:
        payload["per_page"] = total_count

    r = requests.get(
        "https://api.gandi.net/v5/domain/domains",
        headers={"authorization": f'Apikey {os.getenv("GANDI_KEY")}'},
        params=payload,
    )
    r.raise_for_status()
    return r.json()


def parse_content(content):
    entries = dict()
    for line in content.splitlines():
        words = line.strip().split(" ", maxsplit=4)
        r_name = words[0]
        r_type = words[3]
        ttl = int(words[1])
        value = words[4].replace('"', '\\"')
        key = f"{r_name}_{r_type.lower()}".replace("@", "apex")

        if r_type == "SOA":
            continue

        if key[0].isnumeric():
            key = f"_{key}"
        elif key[0] == "*":
            key = key[1:]

        key = key.replace(".", "_")
        if key in entries:
            entries.get(key).values.append(value)
        else:
            entries[key] = Record(r_name, r_type, ttl, value)
    return entries


def generate_tf(domain, entries, subdir):
    if subdir:
        try:
            os.mkdir(f"./{domain}")
        except OSError as error:
            raise Exception(f"Error in generate_tf os.mkdir failed with error: {error}")
        filename = f"./{domain}/main.tf"
        filename_tfimport = f"./{domain}/main.tfimport"
    else:
        filename = f"{domain}.tf"
    tf_name = domain.replace(".", "_")
    # TF resource can't start with a number, it should start with either _ or a letter
    # so domain like 1984.com can have a valid file.
    try:
        int(tf_name[0])
        tf_name = "_" + tf_name
    except ValueError:
        pass
    commands = []
    with click.open_file(filename, "w") as f:
        f.write("locals {\n")
        f.write(f"  {tf_name}_records = " + "{\n")

        for key, record in entries.items():
            f.write(f"    {key} = {{\n")
            f.write(f'      name = "{record.name}"\n')
            f.write(f'      type = "{record.r_type}"\n')
            f.write(f"      ttl  = {record.ttl}\n")
            f.write("      values = [\n")

            for value in record.values:
                f.write(f'        "{value}",\n')
            f.write("      ]\n")
            f.write("    }\n")

            commands.append(
                "terraform import "
                f"'gandi_livedns_record.{tf_name}[\"{key}\"]' "
                f'"{domain}/{record.name}/{record.r_type}"'
            )

        f.write("  }\n}\n\n")

        f.write(f'resource "gandi_livedns_record" "{tf_name}" {{\n')
        f.write(f"  for_each = local.{tf_name}_records\n\n")
        f.write(f'  zone = "{domain}"\n\n')
        f.write("  name   = each.value.name\n")
        f.write("  ttl    = each.value.ttl\n")
        f.write("  type   = each.value.type\n")
        f.write("  values = each.value.values\n")
        f.write("}\n")
    if subdir is True:
        with click.open_file(filename_tfimport, "w") as fi:
            for cmd in commands:
                fi.write(f"{cmd}\n")
    return commands


@click.command()
@click.option("--version", help="Display version information", is_flag=True)
@click.option("--organization-id", help="Filter domains owned by this organization id only", default=None)
@click.option(
    "--subdir", help="Create a sub-directory to store generated domain tf code and tf import commands.", is_flag=True
)
@click.argument("domains", nargs=-1)
def generate(domains, version, organization_id, subdir):
    """
    Command to read Gandi.net live DNS records and generate corresponding TF
    gandi_livedns_record resources. If no domain name is given, it will fetch
    all available, optionally filtered by the organiyation id.

    Warning: nameserver type 'other' and 'abc' cannot be managed via the gandi
    terraform provider, therefore they will not be retrieved.
    .
    """
    if version:
        import importlib.metadata

        _version = importlib.metadata.version("gandi-2-terraform")
        click.echo(f"Version {_version}")
        return

    if len(domains) == 0:
        domains = tuple([domain["fqdn_unicode"] for domain in fetch_domains_list(organization_id)])
        if len(domains) == 0:
            click.echo("No domain found")

    commands = []
    for domain in domains:
        content = fetch_records(domain)
        entries = parse_content(content)
        commands += generate_tf(domain, entries, subdir)
    if subdir is False:
        for cmd in commands:
            click.echo(cmd)


if __name__ == "__main__":
    generate()
