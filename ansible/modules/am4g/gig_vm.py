#!/usr/bin/python

# Copyright: (c) 2018, Terry Jones <terry.jones@example.org>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: gig_vm

short_description: This module will create or delete a vm on GIG based clouds.
version_added: "1.0.0"

description: Using this module you can create and delete virtual machines on GIG based clouds.

options:
    api_url:
        description: URL of the portal. Example https://cloud.example.com
        required: true
        type: str
    jwt:
        description: JWT to authorize to the portal
        required: true
        type: str
    customer_id:
        description: Customer ID found in the portal
        required: true
        type: str
    cloudspace_id:
        description: The ID of the cloudspace where the VM (should) exist
        required: true
        type: str
    state:
        description:
        - State can be present or absent
        - present: Your vm will be created if it doesn't exist yet (default)
        - absent: Your vm will be deleted if it exists
        required: false
        type: str
        default: "present"
    name:
        description: Name of the VM
        required: false
        type: str
    vm_id:
        description: ID of the VM. You can only delete/change vm's when passing the vm_id. You can't create a vm with a particular vm_id
        required: false
        type: int
    image_id
        description: ID of the image (for now required. Using image name / snapshot / iso is not implemented yet)
        required: True
        type: int
    name:
        description: Description of the VM
        required: false
        type: str
    vcpus:
        description: Number of vcpus
        required: false
        default: 1
        type: int
    memory:
        description: Amount of memory in MB
        required: false
        default: 1024
        type: int
    disk_size:
        description: Disk size of the bootdisk in GB
        required: false
        default: 30
        type: int
    user_data:
        description: User data for the vm. The userdata should be passed in json format
        required: false
        type: json
    enable_vm_agent:
        description: Boolean to enable the VM agent
        required: false
        default: false
        type: bool
    boot_type:
        description: Boottype of the VM (bios, uefi)
        required: false
        type: str
        default: 'bios'
    private_ip:
        description: Private IP to assign in the cloudspace network
        required: false
        type: str
    ephemeral_disks:
        description: List of datadisks to attach to the VM. Each element is an integer for the size in GB. These disks will be deleted when you remove the VM
        required: false
        type: list[int]
    permanently_delete
        description: Only applicable when state: absent. If set to true, vm won't be kept around in the recycle bin
        required: false
        type: bool
        default: false
    external_networks:
        description: 
        - List of external networks to configure.
        - Each network is a dict with network, kind, ip as keys. 
        - network: external_network_id
        - kind: kind of virtual interface
        - ip: IP Address in the external network
        required: false
        type: list[dict]
    persistent_disks:
        description: List of disks to attach to the VM. Each element is an integer for the ID of the disk. These disks will be detached when you remove the VM.
        required: false
        type: list[int]
author:
    - Kevin Hunyadi (@KevinHun)
'''

EXAMPLES = r'''
# Create a vm
- name: test vm creation
  hosts: localhost
  tasks:
  - name: Create vm if needed
    gig_vm:
      api_url: 'https://cloud.example.com'
      jwt: 'myjwt
      cloudspace_id: "mycloudspace"
      customer_id: "mycustomer_1"
      state: 'present'
      name: "My Ansible VM"
      description: "vm created by ansible"
      vcpus: 2
      memory: 2048
      private_ip: ""
      image_id: 45
      disk_size: 30
      enable_vm_agent: false
      boot_type: "bios"
      user_data: {hostname: "AnsibleVM"}
      external_networks:
      - network: 3
        kind: virtio
        ip: "x.x.x.x"
      - network: 3
        kind: virtio
        ip: "x.x.x.x"
      - network: 3
        kind: virtio
        ip: "x.x.x.x"
      persistent_disks:
      - 4930
      - 4931
      ephemeral_disks:
      - 30
      - 40
      - 50
'''

RETURN = r'''
status:
    description: Status of the VM after running the module.
    type: str
    returned: always
    sample: 'VM CREATED'
changed:
    description: Check if changes were made.
    type: boolean
    returned: always
    sample: False
'''

import pc4g
import time
from ansible.module_utils.basic import AnsibleModule

class BadVMConfig(Exception):

    def __init__(self, reason):
            self.reason = reason

    def __str__(self):
        """Custom error messages for exception"""
        error_message = f'Reason: {self.reason}\n'
        return error_message

class Vmachine(object):
    def __init__(self, api_url, jwt, customer_id, cloudspace_id, vm_id=None, name=None, state='present', **args):
        # Set authentication to communicate with the cloud api
        configuration = pc4g.Configuration()
        configuration.host = api_url
        configuration.api_key['Authorization'] = jwt
        configuration.api_key_prefix['Authorization'] = 'Bearer'
        # create api instance
        self.customer_api = pc4g.CustomersApi(pc4g.ApiClient(configuration))
        self.customer_id = customer_id
        self.cloudspace_id = cloudspace_id
        self.state = state
        if vm_id:
            self.vm_id = vm_id
            self.vm_info = self._find_vm_by_id(vm_id)
            self.exists = True
            # Got VM by id. Check if name has to change
            if name != self.vm_info.name:
                self.name_to_be = name
        else:
            self.vm_info = self._find_vm_by_name(name)
            if self.vm_info:
                self.exists = True
            else:
                self.name_to_be = name
                self.exists = False

        self.extra_args = args

    def _find_vm_by_name(self, name):
        vm_list = self.customer_api.list_cloudspace_virtual_machines(self.customer_id, self.cloudspace_id).result
        if not vm_list:
            return None
        for vm in vm_list:
            if vm.name == name:
                self.vm_id = vm.vm_id
                return self._find_vm_by_id(vm.vm_id)
        else:
            return None

    def _find_vm_by_id(self, vm_id):
        try:
            vm_info = self.customer_api.get_virtual_machine_info(self.customer_id, self.cloudspace_id, vm_id)
            return vm_info
        except pc4g.rest.ApiException as e:
            if e.status == 404:
                raise BadVMConfig(f'VM with vm_id {vm_id} does not exist.')
            elif e.status == 400:
                raise BadVMConfig(e.body)
    
    def do_changes(self):
        print("Changing VM's is not implemented yet.")
        return False
    
    def create_vm(self):
        # Check parameters:
        if not self.extra_args['image_id']:
            raise BadVMConfig(f'Can\'t create vm with name {self.name_to_be} without an image_id configured.')
            ####
        payload = {'userdata': self.extra_args['user_data']} if self.extra_args['user_data'] else {}
        external_networks = self.extra_args['external_networks'] if self.extra_args['external_networks'] else []
        persistent_disks = self.extra_args['persistent_disks'] if self.extra_args['persistent_disks'] else []

        ephemeral_disks = self.extra_args.get("ephemeral_disks")
        if ephemeral_disks:
            self.extra_args["data_disks"] = ephemeral_disks

        for remove in ["user_data", "permanently_delete", "external_networks", "persistent_disks", "ephemeral_disks"]:
            if remove in self.extra_args: 
                del self.extra_args[remove]

        vm_create_resp = self.customer_api.create_virtual_machine(self.customer_id, self.cloudspace_id, self.name_to_be, payload=payload, **self.extra_args)
        self.vm_id = vm_create_resp.vm_id
        # Add external networks
        if external_networks:
            self._configure_external_networks(external_networks)
        # Attach disks
        if persistent_disks:
            self._attach_extra_disks(persistent_disks)

        return True

    def delete_vm(self, permanently):
        persistent_disks = self.extra_args['persistent_disks'] if self.extra_args['persistent_disks'] else []
        if persistent_disks:
            # Detach persistent disks first
            self._detach_extra_disks(persistent_disks)

        self.customer_api.delete_virtual_machine(self.customer_id, self.cloudspace_id, self.vm_id, permanently=permanently)
        return True

    def _configure_external_networks(self, external_networks):
        for ext_net in external_networks:
            self._wait_vm_running_status()
            self.customer_api.attach_external_networks_virtual_machine(self.customer_id, self.cloudspace_id, self.vm_id, ext_net['network'], model=ext_net['kind'], external_network_ip=ext_net['ip'] )

    def _attach_extra_disks(self, disks):
        for disk in disks:
            self._wait_vm_running_status()
            self.customer_api.attach_disk_virtual_machine(self.customer_id, self.cloudspace_id, self.vm_id, disk)

    def _detach_extra_disks(self, disks):
        for disk in disks:
            self._wait_vm_running_status()
            self.customer_api.detach_disk_virtual_machine(self.customer_id, self.cloudspace_id, self.vm_id, disk)

    def _wait_vm_running_status(self):
        for _ in range(12):
            updated_info = self.customer_api.get_virtual_machine_info(self.customer_id, self.cloudspace_id, self.vm_id)
            if updated_info.status in ("RUNNING", "HALTED"):
                break
            time.sleep(5)
        else:
            RuntimeError("VM not in RUNNING status after 1 minute.")

def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        api_url=dict(type='str', required=True),
        jwt=dict(type='str', required=True),
        customer_id=dict(type='str', required=True),
        cloudspace_id=dict(type='str', required=True),
        state=dict(type='str', required=False, default='present'),
        name=dict(type='str', required=False),
        vm_id=dict(type='int', required=False, default=None),
        image_id=dict(type='int', required=False),
        description=dict(type='str', required=False, default='VM Created by Ansible'),
        vcpus=dict(type='int', required=False, default=1),
        memory=dict(type='int', required=False, default=1024),
        user_data=dict(type='json', required=False, default=None),
        disk_size=dict(type='int', required=False, default=30),
        enable_vm_agent=dict(type='bool', required=False, default=False),
        boot_type=dict(type='str', required=False, default="bios"),
        private_ip=dict(type='str', required=False, default=""),
        ephemeral_disks=dict(type='list', elements='int', required=False, default=None),
        permanently_delete=dict(type='bool', required=False, default=False),
        external_networks=dict(type='list', elements='dict', required=False, default=[]),
        persistent_disks=dict(type='list', elements='int', required=False, default=[])
    )
    
    result = dict(
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    try:
        vm = Vmachine(**module.params)
    except BadVMConfig as e:
        module.fail_json(msg=f'VM configuration is incorrect: { e }', **result)        
    
    # If running check_mode, bail before doing changes.
    if module.check_mode:
        module.exit_json(**result)

    # Create or change VM if needed
    if vm.state == "present":
        if not vm.exists:
            #import epdb; epdb.set_trace()
            changed = vm.create_vm()
            result['status'] = "VM CREATED"
        else:
            changed = False
            result['status'] = "VM PRESENT ALREADY"
    elif vm.state == "change":
            changed = vm.do_changes()
            result['status'] = "VM %s CHANGED"%vm.vm_id if changed else "VM %s DID NOT CHANGE"%vm.vm_id
    elif vm.state == "absent":
        if vm.exists:
            changed = vm.delete_vm(module.params['permanently_delete'])
            result['status'] = "VM DELETED"
        else:
            changed = False
            result['status'] = "VM ABSENT ALREADY"
    else:
        module.fail_json(msg="state '%s' unrecognized"%vm.state)
        raise ValueError("Faulty vm state given.")

    result['changed'] = changed
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
