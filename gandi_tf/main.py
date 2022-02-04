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


def generate_tf(domain, entries):
    filename = f"{domain}.tf"
    tf_name = domain.replace(".", "_")
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

    return commands


@click.command(no_args_is_help=True)
@click.option("--version", help="Display version information", is_flag=True)
@click.argument("domains", nargs=-1)
def generate(domains, version):
    """
    Command to read Gandi.net live DNS records and generate
    corresponding TF gandi_livedns_record resources.
    """
    if version:
        import importlib.metadata

        _version = importlib.metadata.version("gandi-2-terraform")
        click.echo(f"Version {_version}")
        return

    commands = []
    for domain in domains:
        content = fetch_records(domain)
        entries = parse_content(content)
        commands += generate_tf(domain, entries)

    for cmd in commands:
        click.echo(cmd)


if __name__ == "__main__":
    generate()
