import os
import sys
from dotenv import load_dotenv
load_dotenv()  # This loads environment variables from a .env file in the current directory
import asyncio
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.dns import DnsManagementClient

# Console colors for logs
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKORANGE = '\033[38;5;214m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
 
#####
def print_info(msg):
    print(f"{bcolors.OKBLUE}[INFO]{bcolors.ENDC} {msg}")

def print_build(msg):
    print(f"{bcolors.OKORANGE}[BUILD]{bcolors.ENDC} {msg}")

def print_success(msg):
    print(f"{bcolors.OKGREEN}[SUCCESS]{bcolors.ENDC} {msg}")

def print_warn(msg):
    print(f"{bcolors.WARNING}[WARNING]{bcolors.ENDC} {msg}")

def print_error(msg):
    print(f"{bcolors.FAIL}[ERROR]{bcolors.ENDC} {msg}")
    
def prompt_input(prompt, default=None):
    if default:
        prompt_full = f"{prompt} [{default}]: "
    else:
        prompt_full = f"{prompt}: "
    value = input(prompt_full)
    if not value and default:
        return default
    return value

async def delete_vm_and_resources(subscription_id, resource_group, vm_name, domain, a_records):
    try:
        credentials = ClientSecretCredential(
            client_id=os.environ['AZURE_APP_CLIENT_ID'],
            client_secret=os.environ['AZURE_APP_CLIENT_SECRET'],
            tenant_id=os.environ['AZURE_APP_TENANT_ID']
        )
        print_info("Authenticated with Azure successfully.")
    except KeyError:
        print_error("Please set AZURE_APP_CLIENT_ID, AZURE_APP_CLIENT_SECRET, and AZURE_APP_TENANT_ID environment variables.")
        sys.exit(1)

    compute_client = ComputeManagementClient(credentials, subscription_id)
    network_client = NetworkManagementClient(credentials, subscription_id)
    dns_client = DnsManagementClient(credentials, subscription_id)

    print_info(f"Attempting to delete VM '{vm_name}' in resource group '{resource_group}'...")
    try:
        vm = compute_client.virtual_machines.get(resource_group, vm_name)
        os_disk_name = vm.storage_profile.os_disk.name
        compute_client.virtual_machines.begin_delete(resource_group, vm_name).result()
        print_success(f"Deleted VM '{vm_name}'.")
    except Exception as e:
        print_warn(f"Failed to delete VM '{vm_name}': {e}")
        os_disk_name = None

    if os_disk_name:
        try:
            compute_client.disks.begin_delete(resource_group, os_disk_name).result()
            print_success(f"Deleted OS disk '{os_disk_name}'.")
        except Exception as e:
            print_warn(f"Failed to delete OS disk '{os_disk_name}': {e}")

    nic_name = f"{vm_name}-nic"
    try:
        network_client.network_interfaces.begin_delete(resource_group, nic_name).result()
        print_success(f"Deleted NIC '{nic_name}'.")
    except Exception as e:
        print_warn(f"Failed to delete NIC '{nic_name}': {e}")

    nsg_name = f"{vm_name}-nsg"
    try:
        network_client.network_security_groups.begin_delete(resource_group, nsg_name).result()
        print_success(f"Deleted NSG '{nsg_name}'.")
    except Exception as e:
        print_warn(f"Failed to delete NSG '{nsg_name}': {e}")

    public_ip_name = f"{vm_name}-public-ip"
    try:
        network_client.public_ip_addresses.begin_delete(resource_group, public_ip_name).result()
        print_success(f"Deleted Public IP '{public_ip_name}'.")
    except Exception as e:
        print_warn(f"Failed to delete Public IP '{public_ip_name}': {e}")

    vnet_name = f"{vm_name}-vnet"
    try:
        network_client.virtual_networks.begin_delete(resource_group, vnet_name).result()
        print_success(f"Deleted VNet '{vnet_name}'.")
    except Exception as e:
        print_warn(f"Failed to delete VNet '{vnet_name}': {e}")

    # Delete DNS A records
    for record_name in a_records:
        record_to_delete = record_name if record_name else '@'  # '@' for root domain
        try:
            dns_client.record_sets.delete(resource_group, domain, record_to_delete, 'A')
            print_success(f"Deleted DNS A record '{record_to_delete}' in zone '{domain}'.")
        except Exception as e:
            print_warn(f"Failed to delete DNS A record '{record_to_delete}' in zone '{domain}': {e}")

    print_success("Deletion process completed.")

if __name__ == "__main__":
    vm_name = prompt_input("Enter the VM name to delete","search")
    if not vm_name.strip():
        print_error("VM name cannot be empty. Exiting.")
        sys.exit(1)
    resource_group = prompt_input("Enter the resource group name","searchgroup")
    domain = prompt_input("Enter the DNS zone domain name (e.g., example.com)","example.com")
    a_records_input = vm_name  # single record name string, so split works
    a_records = [r.strip() for r in a_records_input.split(",")]

    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not subscription_id:
        print_error("Please set the AZURE_SUBSCRIPTION_ID environment variable.")
        sys.exit(1)

    asyncio.run(delete_vm_and_resources(subscription_id, resource_group, vm_name, domain, a_records))
