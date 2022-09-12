import os, sys
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
    if organization_id is not None:
        fh_url = f"https://api.gandi.net/v5/domain/domains?per_page=1&sort_by=fqdn&sharing_id={organization_id}"
    else:
        fh_url = f"https://api.gandi.net/v5/domain/domains?per_page=1&sort_by=fqdn"
    ## Get total count of domain & fetch all in one page
    fake_head = requests.get(
        fh_url,
        headers={"authorization": f'Apikey {os.getenv("GANDI_KEY")}'},
    )
    fake_head.raise_for_status()
    total_count = fake_head.headers["total-count"]
    if organization_id is not None:
        get_url = f"https://api.gandi.net/v5/domain/domains?per_page={total_count}&sort_by=fqdn&sharing_id={organization_id}"
    else:
        get_url = f"https://api.gandi.net/v5/domain/domains?per_page={total_count}&sort_by=fqdn"
    r = requests.get(
        get_url,
        headers={"authorization": f'Apikey {os.getenv("GANDI_KEY")}'},
    )
    r.raise_for_status()
    return r.json()


def print_domains_list(domains, list_domains_details, nsfilters):
    if list_domains_details is True:
        for domain in domains:
            if domain['nameserver']['current'] in nsfilters:
                print(domain)
    else:
        for domain in domains:
            if domain['nameserver']['current'] in nsfilters:
                print(domain["fqdn_unicode"])


def fetch_organizations_list():
    r = requests.get(
        "https://api.gandi.net/v5/organization/organizations",
        headers={"authorization": f'Apikey {os.getenv("GANDI_KEY")}'},
    )
    r.raise_for_status()
    return r.json()


def print_organizations_list(organizations):
    for organization in organizations:
        print(organization)


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
    if subdir is True:
        try:
            os.mkdir( f"./{domain}", 0o755 )
        except OSError as error:
            raise Exception(f"Error in generate_tf os.mkdir failed with error:{error}")
        filename = f"./{domain}/{domain}.tf"
        filename_tfimport = f"./{domain}/{domain}.tfimport"
    else:
        filename = f"{domain}.tf"
    tf_name = domain.replace(".", "_")
    ## TF resource can't start with number should be either _ or a letter so domain like 1984.com will generate error with terraform
    try:
        c0 = int(tf_name[0])
        tf_name = "_" + tf_name
    except ValueError as e:
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


@click.command(no_args_is_help=True)
@click.option("--version", help="Display version information", is_flag=True)
@click.option("--organization_id", help="Gandi organization ID (passing an organization ID will limit query on domain own by organization)", default=None)
@click.option("--list_domains", help="Fetch and display fqdn_unicode", is_flag=True)
@click.option("--list_domains_details", help="Fetch and display all domain details", is_flag=True)
@click.option("--list_organizations", help="Fetch and display all organizations details", is_flag=True)
@click.option('--nsfilters', help="Filter domaine based on their current nameserver 'abc','livedns' or 'other'. You can add multiple filter Example: gandi2tf --list_domains --nsfilters abc --nsfilters livedns)", multiple=True, default=[
'abc','livedns','other'])
@click.option("--auto_generate", help="Auto-generate tf resource based on domain from gandi instead of STDIN/USERINPUT (option can be used with --organization_id, --subdir and multiple --nsfilters)", is_flag=True)
@click.option("--subdir", help="Create a sub-directory to store generated domain tf and tf import command", is_flag=True)
@click.argument("domains", nargs=-1)
def generate(domains, version, organization_id, list_domains, list_domains_details, list_organizations, nsfilters, auto_generate, subdir):
    """
    Command to read Gandi.net live DNS records and generate
    corresponding TF gandi_livedns_record resources.

    Warning: nameserver type 'other' and 'abc' can't be managed via terraform (for abc domain you can transfer them to livedns on gandi webinterface)
    """
    for filter in nsfilters:
        if filter not in ['abc','livedns','other']:
            print(f"nsfilters error available filter: 'abc', 'livedns' or 'other' you submitted {nsfilters}")
            return
    if version:
        import importlib.metadata

        _version = importlib.metadata.version("gandi-2-terraform")
        click.echo(f"Version {_version}")
        return
    if list_domains:
        print_domains_list(fetch_domains_list(organization_id), list_domains_details, nsfilters)
        return
    if list_domains_details:
        print_domains_list(fetch_domains_list(organization_id), list_domains_details, nsfilters)
        return
    if list_organizations:
        print_organizations_list(fetch_organizations_list())
        return
    if auto_generate:
        domains = []
        fetch_domains = fetch_domains_list(organization_id)
        for domain in fetch_domains:
            if domain['nameserver']['current'] in nsfilters:
                if "other" in domain['nameserver']['current']:
                    print("Your are trying to auto_generate a tf from a domain not managed by Gandi check tour nsfilters")
                    return
                else:
                    domains.append(domain["fqdn_unicode"])
        if domains == []:
            print("--auto_generate was used but did not return any domain check your cmd line or use less restrictive nsfilters")
        
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
