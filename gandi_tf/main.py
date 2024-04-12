"""Main module for the CLI."""

import os

import click
import requests


# pylint: disable = too-few-public-methods
class Record:
    """
    Class representing the TF record entries to write out.
    """

    def __init__(self, name, r_type, ttl, value) -> None:
        self.name = name
        self.r_type = r_type
        self.ttl = ttl
        self.values = [value]


def fetch_records(domain):
    """
    Fetch DNS records for a given domain name.
    """
    req = requests.get(
        f"https://dns.api.gandi.net/api/v5/domains/{domain}/records",
        headers={**{"Accept": "text/plain"}, **get_authentication_header()},
        timeout=5,
    )
    req.raise_for_status()
    return req.text


def fetch_domains_list(organization_id):
    """
    Fetch domains of the API key account, optionally filtered by the given
    organization id.
    """
    payload = {"per_page": 1, "sort_by": "fqdn", "nameserver": "livedns"}
    if organization_id is not None:
        payload["sharing_id"] = organization_id

    # Get total count of domain to fetch them all in one request
    fake_head = requests.get(
        "https://api.gandi.net/v5/domain/domains",
        headers=get_authentication_header(),
        params=payload,
        timeout=5,
    )
    fake_head.raise_for_status()

    try:
        total_count = int(fake_head.headers.get("total-count", 0))
    except ValueError:
        total_count = 0
    if total_count > 0:
        payload["per_page"] = total_count

    req = requests.get(
        "https://api.gandi.net/v5/domain/domains",
        headers=get_authentication_header(),
        params=payload,
        timeout=5,
    )
    req.raise_for_status()
    return req.json()


def get_authentication_header():
    """
    Returns the correct authentication header based on the GANDI_KEY environment variable.
    """
    key = os.getenv("GANDI_KEY", "")
    header = "Apikey" if len(key) < 25 else "Bearer"
    return {"Authorization": f"{header} {key}"}


def parse_content(content):
    """
    Parser for the API response to return a list of Record objects."""
    entries = {}
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
    """
    Generate the Terraform files for the gandi provider with gandi_livedns_record
    resources.
    """
    if subdir:
        try:
            os.mkdir(f"./{domain}")
        except OSError as error:
            click.echo(f"Error in generate_tf os.mkdir failed with error: {error}")
            raise error
        filename = f"./{domain}/main.tf"
        filename_tfimport = f"./{domain}/main.tfimport"
    else:
        filename = f"{domain}.tf"

    # TF resource can't start with a number, it should start with either _ or a letter
    tf_name = domain.replace(".", "_")
    try:
        int(tf_name[0])
        tf_name = "_" + tf_name
    except ValueError:
        pass

    commands = []
    with click.open_file(filename, "w") as file:
        file.write("locals {\n")
        file.write(f"  {tf_name}_records = " + "{\n")

        for key, record in entries.items():
            file.write(f"    {key} = {{\n")
            file.write(f'      name = "{record.name}"\n')
            file.write(f'      type = "{record.r_type}"\n')
            file.write(f"      ttl  = {record.ttl}\n")
            file.write("      values = [\n")

            for value in record.values:
                file.write(f'        "{value}",\n')
            file.write("      ]\n")
            file.write("    }\n")

            commands.append(
                "terraform import "
                f"'gandi_livedns_record.{tf_name}[\"{key}\"]' "
                f'"{domain}/{record.name}/{record.r_type}"'
            )

        file.write("  }\n}\n\n")

        file.write(f'resource "gandi_livedns_record" "{tf_name}" {{\n')
        file.write(f"  for_each = local.{tf_name}_records\n\n")
        file.write(f'  zone = "{domain}"\n\n')
        file.write("  name   = each.value.name\n")
        file.write("  ttl    = each.value.ttl\n")
        file.write("  type   = each.value.type\n")
        file.write("  values = each.value.values\n")
        file.write("}\n")

    if subdir:
        with click.open_file(filename_tfimport, "w") as file:
            for cmd in commands:
                file.write(f"{cmd}\n")

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
    CLI to read Gandi.net liveDNS records and generate corresponding TF
    gandi_livedns_record resources. If no domain name is given, it will fetch
    all available domains accessible by the API key, optionally filtered by
    the organiyation id.

    Warning: nameserver type 'other' and 'abc' cannot be managed via the gandi
    terraform provider, therefore they will not be retrieved.
    """
    if version:
        # pylint: disable = import-outside-toplevel
        import importlib.metadata

        _version = importlib.metadata.version("gandi-2-terraform")
        click.echo(f"Version {_version}")
        return

    if len(domains) == 0:
        domains = tuple(domain["fqdn_unicode"] for domain in fetch_domains_list(organization_id))
        if len(domains) == 0:
            click.echo("No domain found")

    commands = []
    for domain in domains:
        content = fetch_records(domain)
        entries = parse_content(content)
        commands += generate_tf(domain, entries, subdir)

    if not subdir:
        for cmd in commands:
            click.echo(cmd)


if __name__ == "__main__":
    # pylint: disable = no-value-for-parameter
    generate()
