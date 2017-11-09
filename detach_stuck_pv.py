#!/usr/bin/env python

import subprocess
import json
import datetime
import time
import re
import sys
from datetime import datetime

class VolumeInfo(object):
    def __init__(self, pv_name, ebs_id, instance_id, device_name):
        self.pv_name = pv_name
        self.ebs_id = ebs_id
        self.instance_id = instance_id
        self.device_name = device_name

class AttachedVolume(object):
    def __init__(self, profile, region):
        self.profile = profile
        self.region = region
        self.pvc_regex = re.compile("^pvc")

    def run(self):
        for line in sys.stdin.readlines():
            if self.pvc_regex.match(line):
                line = line.strip()
                pv_array = line.split(":")
                pv_name = pv_array[0].strip()
                ebs_id = pv_array[1].strip()
                self.check_volume(ebs_id, pv_name)
        self.check_attaching_volumes()


    def check_volume(self, ebs_id, pv_name):
        try:
            output = subprocess.check_output(["aws", "ec2", "describe-volumes", "--volume-ids", ebs_id, "--profile", self.profile, "--region", self.region])
            ebs_data = json.loads(output)
            volume = ebs_data["Volumes"][0]
            state = volume["State"]
            if state == "in-use":
                attachment = volume["Attachments"][0]
                instance_id = attachment["InstanceId"]
                device_name = attachment["Device"]
                volume_info = VolumeInfo(pv_name, ebs_id, instance_id, device_name)
                if not self.check_for_mount(volume_info):
                    print "Detaching volume %s from node %s" % (ebs_id, volume_info.instance_id)
                    self.detach_volumes(ebs_id)
        except Exception, e:
            print "Volume not found"

    def check_attaching_volumes(self):
        volume_dict = self.get_volume_json()
        dirty_nodes = {}
        if volume_dict:
            volumes = volume_dict["Volumes"]
            for volume in volumes:
                if self.stuck_in_attaching(volume):
                    attachment = volume["Attachments"][0]
                    dirty_nodes[attachment["InstanceId"]] = volume

        for node, volume in dirty_nodes.iteritems():
            print "Node %s has dirty volumes " % node

        reboot_nodes_answer = self.yes_no("Do you want to reboot those nodes")
        if reboot_nodes_answer:
            for node, volume in dirty_nodes.iteritems():
                print "Rebooting node %s" % node
                subprocess.check_output(["aws", "ec2", "reboot-instances", "--instance-ids", node, "--profile", self.profile, "--region", self.region])


    def yes_no(self, answer):
        yes = set(['yes','y', 'ye', ''])
        no = set(['no','n'])

        while True:
            choice = raw_input(answer).lower()
            if choice in yes:
                return True
            elif choice in no:
                return False
            else:
                print "Please respond with 'yes' or 'no'\n"


    def stuck_in_attaching(self, volume):
        attachments = volume["Attachments"]
        if len(attachments) > 0:
            attachment = attachments[0]
            state = attachment["State"]
            instance = attachment["InstanceId"]
            volume_id = attachment["VolumeId"]
            attach_time = attachment["AttachTime"]
            return self.check_attaching_time(state, attach_time)
        else:
            return False

    def check_attaching_time(self, state, attach_time_str):
        if state == "attaching":
            attach_time = datetime.strptime(attach_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            time_diff = datetime.utcnow() - attach_time
            diff_in_minutes = time_diff.total_seconds() / 60
            # if stuck for more than 30 minutes
            return (diff_in_minutes > 30)
        else:
            return False

    def get_volume_json(self):
        try:
            output = subprocess.check_output(["aws", "ec2", "describe-volumes", "--profile", self.profile, "--region", self.region])
            all_volumes = json.loads(output)
            return all_volumes
        except Exception, e:
            print "Error getting volums"
            return {}



    def detach_volumes(self, ebs_id):
        try:
            subprocess.check_output(["aws", "ec2", "detach-volume", "--volume-id", ebs_id, "--profile", self.profile, "--region", self.region])
        except Exception, e:
            print "Error while detaching volume %s" % (ebs_id)


    def check_for_mount(self, volume_info):
        try:
            # running command
            # ossh -o "StrictHostKeyChecking=no" -c "grep \/dev\/xvdbz /proc/mounts" i-foobar
            grep_command = "grep %s /proc/mounts" % (volume_info.ebs_id)
            exec_command = ["ossh", "-o", "StrictHostKeyChecking=no", "-c", grep_command, volume_info.instance_id]
            output = subprocess.check_output(exec_command)
            if volume_info.device_name in output:
                return True
            else:
                return False
        except Exception, e:
            return False

if __name__ == "__main__":
    a = AttachedVolume(sys.argv[1], sys.argv[2])
    a.run()
