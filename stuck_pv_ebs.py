#!/usr/bin/env python

import subprocess
import json
import datetime
import time
import re
import argparse

class PVC(object):
    def __init__(self, pvc_name, namespace):
        self.namespace = namespace
        self.pvc_name = pvc_name

    def get_pv_name(self):
        output = subprocess.check_output(['oc', 'get', 'pvc', self.pvc_name, '-n', self.namespace, '-o', 'json'])
        pvc_json = json.loads(output)
        return pvc_json['spec']['volumeName']

class RC(object):
    """
    ReplicationController
    """
    def __init__(self, name, namespace):
        self.name = name
        self.namespace = namespace
        self.load()

    def load(self):
        output = subprocess.check_output(['oc', 'get', 'rc', self.name, '-n', self.namespace, '-o', 'json'])
        j = json.loads(output)
        self.replicas = j['status'].get('replicas', '')
        self.available_replicas = j['status'].get('availableReplicas', '0')

class Pod(object):
    def __init__(self, pod_data):
        self.pod_data = pod_data
        self.pod_name = pod_data['metadata']['name']
        self.namespace = pod_data['metadata']['namespace']
        self.uid = pod_data['metadata']['uid']
        start_time = pod_data['status']['startTime']
        self.start_time =  datetime.datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%SZ')
        self.host_ip = pod_data['status']['hostIP']
        self.rc_name = ""
        if pod_data['metadata'].has_key('annotations') and pod_data['metadata']['annotations'].has_key('kubernetes.io/created-by'):
            created_by_reference = json.loads(pod_data['metadata']['annotations']['kubernetes.io/created-by'])
            if created_by_reference['reference']['kind'] == 'ReplicationController':
                self.rc_name = created_by_reference['reference']['name']

    def pvc_names(self):
        pvc_claims = []
        for volume in self.pod_data['spec']['volumes']:
            if 'persistentVolumeClaim' in volume:
                pvc_claims.append(PVC(volume['persistentVolumeClaim']['claimName'], self.namespace))
        return pvc_claims

    def stuck_since(self):
        time_diff = time.time() - time.mktime(self.start_time.timetuple())
        return repr(time_diff / 60.00)

class PodAlert(object):
    def __init__(self):
        self.FAILED_REGEXP = re.compile(r".+FailedMount.+", re.MULTILINE|re.DOTALL)

    def run(self):
        creating_pods = self.get_creating_pods()
        for pod in creating_pods:
            pv_check = self.check_for_pv_event(pod)


    def get_creating_pods(self):
        """
        get pods in creating state
        """
        output = subprocess.check_output(['oc', 'get', 'pods', '--all-namespaces', '-o', 'json'])
        pod_json = json.loads(output)
        pod_items = pod_json['items']
        creating_pods = []
        for pod in pod_items:
            pod_status = pod['status']
            if pod_status['phase'] == 'Pending':
                if 'containerStatuses' in pod_status:
                    pod_container_statuses = pod['status']['containerStatuses']
                    for pod_state in pod_container_statuses:
                        reason = pod_state.get('state', {}).get('waiting', {}).get('reason', '')
                        if reason == 'ContainerCreating':
                            creating_pods.append(Pod(pod))
                            break


        return creating_pods

    def check_for_pv_event(self, pod):
        """
        Check for PV event
        """
        time_diff = time.time() - time.mktime(pod.start_time.timetuple())
        if time_diff >= 300:
            output = subprocess.check_output(['oc', 'describe', 'pod', '-n', pod.namespace, pod.pod_name])
            if self.pod_has_pv_event(output):
                pv_name, pvc_name, ebs, rc_name, rc_count = self.get_pv_name(pod)
                print "Pod: %s %s PVC: %s PV: %s AWS ID: %s RC: %s %s" % (pod.namespace, pod.pod_name, pvc_name, pv_name, ebs, rc_name, rc_count)

    def get_pv_name(self, pod):
        pvc = pod.pvc_names()[0]
        pv_name = pvc.get_pv_name()
        output = subprocess.check_output(['oc', 'get', 'pv', pv_name, '-o', 'json'])
        pv_json = json.loads(output)
        rc_name = ""
        rc_count = ""
        if pod.rc_name != "":
            rc = RC(pod.rc_name, pod.namespace)
            rc_name = rc.name
            rc_count = "%s/%s" % (rc.available_replicas, rc.replicas)
        return pv_name, pvc.pvc_name, pv_json['spec']['awsElasticBlockStore']['volumeID'], rc_name, rc_count


    def pod_has_pv_event(self, output):
        return self.FAILED_REGEXP.match(output.strip())

description="""Prints all pods that are ContainerCreating and have FailedMount event.

Pod: pod namespace / name
PVC: PVC name
PV: PV name
AWS ID: ID of EBS volume in Amazon
RC: ReplicationController that created the pod + current replica / requested replica count

When a volume is used in Pod template in ReplicationController (Deployment,
DeploymentConfig, ...), only one pod in the RC can actually use the volume.
In other words, anything else than '/1' is likely user error.
"""

parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.parse_args()
a = PodAlert()
a.run()
