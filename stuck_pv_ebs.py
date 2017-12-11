#!/usr/bin/env python

import subprocess
import json
import datetime
import time
import re


class PVC(object):
    def __init__(self, pvc_name, namespace):
        self.namespace = namespace
        self.pvc_name = pvc_name

    def get_pv_name(self):
        output = subprocess.check_output(['oc', 'get', 'pvc', self.pvc_name, '-n', self.namespace, '-o', 'json'])
        pvc_json = json.loads(output)
        return pvc_json['spec']['volumeName']


class Pod(object):
    def __init__(self, pod_data):
        self.pod_data = pod_data
        self.pod_name = pod_data['metadata']['name']
        self.namespace = pod_data['metadata']['namespace']
        self.uid = pod_data['metadata']['uid']
        start_time = pod_data['status']['startTime']
        self.start_time =  datetime.datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%SZ')
        self.host_ip = pod_data['status']['hostIP']

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
                pv_name, pvc_name, pv = self.get_pv_name(pod)
                print "%s : %s" % (pv_name, pv)

    def get_pv_name(self, pod):
        pvc_name = pod.pvc_names()[0]
        pv_name = pvc_name.get_pv_name()
        output = subprocess.check_output(['oc', 'get', 'pv', pv_name, '-o', 'json'])
        pv_json = json.loads(output)
        return pv_name, pvc_name, pv_json['spec']['awsElasticBlockStore']['volumeID']


    def pod_has_pv_event(self, output):
        return self.FAILED_REGEXP.match(output.strip())


a = PodAlert()
a.run()
