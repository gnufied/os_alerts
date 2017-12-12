#!/usr/bin/env python

import subprocess
import json
import datetime
import time
import re


class PersistentVolume(object):
    def __init__(self, pv_data):
        self.pv_data = pv_data
        self.pv_name = pv_data['metadata']['name']
        volume_id = pv_data['spec']['awsElasticBlockStore']['volumeID']
        volume_array = volume_id.split("/")
        self.ebs_id = volume_array[-1]

class PersistentVolumeClaim(object):
    def __init__(self, pvc_data):
        self.pvc_name = pvc_data['metadata']['name']
        self.namespace = pvc_data['metadata']['namespace']
        self.volume = pvc_data['spec'].get('volumeName', '')

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
        start_time = pod_data.get('status', {}).get('startTime', None)
        if start_time:
            self.start_time =  datetime.datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%SZ')
        host_ip = pod_data.get('status', {}).get('hostIP', None)
        if host_ip:
            self.host_ip = host_ip

    def pvc_names(self):
        pvc_claims = []
        for volume in self.pod_data['spec']['volumes']:
            if 'persistentVolumeClaim' in volume:
                pvc_claims.append(PVC(volume['persistentVolumeClaim']['claimName'], self.namespace))
        return pvc_claims

    def stuck_since(self):
        time_diff = time.time() - time.mktime(self.start_time.timetuple())
        return repr(time_diff / 60.00)


class StuckPods(object):
    PVC_CACHE = {}

    def __init__(self):
        self.FAILED_REGEXP = re.compile(r".+FailedMount.+", re.MULTILINE|re.DOTALL)

    def run(self):
        all_pods = self.get_all_pods()
        all_pv = self.get_all_pv()
        self.get_all_pvc()

        creating_pods = self.get_creating_pods(all_pods)
        for pod in creating_pods:
            self.check_for_pv_event(pod)

        unused_volumes = self.get_unused_volumes(all_pods, all_pv)
        for pv in unused_volumes:
            print "%s : %s" % (pv.pv_name, pv.ebs_id)


    def get_all_pods(self):
        output = subprocess.check_output(['oc', 'get', 'pods', '--all-namespaces', '-o', 'json'])
        pod_json = json.loads(output)
        pod_items = pod_json['items']
        running_pods = []
        for pod in pod_items:
            running_pods.append(Pod(pod))
        return running_pods

    def get_all_pvc(self):
        output = subprocess.check_output(['oc', 'get', 'pvc', '--all-namespaces', '-o', 'json'])
        pvc_json = json.loads(output)
        pvc_items = pvc_json['items']
        all_pvcs = []
        for pvc in pvc_items:
            pvc_object = PersistentVolumeClaim(pvc)
            StuckPods.PVC_CACHE[pvc_object.pvc_name + ":" + pvc_object.namespace] = pvc_object

    def get_creating_pods(self, all_pods):
        "pods in container creating state"
        creating_pods = []
        for pod in all_pods:
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
        if not pod.start_time:
            return

        time_diff = time.time() - time.mktime(pod.start_time.timetuple())
        if time_diff >= 600:
            output = subprocess.check_output(['oc', 'describe', 'pod', '-n', pod.namespace, pod.pod_name])
            if self.pod_has_pv_event(output):
                pv = self.get_pv_name(pod)
                print "%s : %s" % (pv.pv_name, pv.ebs_id)

    def get_pv_name(self, pod):
        pvc_name = pod.pvc_names()[0]
        pv_name = pvc_name.get_pv_name()
        output = subprocess.check_output(['oc', 'get', 'pv', pv_name, '-o', 'json'])
        pv_json = json.loads(output)
        return PersistentVolume(pv_json)

    def pod_has_pv_event(self, output):
        return self.FAILED_REGEXP.match(output.strip())


    def get_all_pv(self):
        output = subprocess.check_output(['oc', 'get', 'pv', '-o', 'json'])
        pv_json = json.loads(output)
        pv_items = pv_json['items']
        all_pv = []
        for pv in pv_items:
            pv_object = PersistentVolume(pv)
            all_pv.append(pv_object)
        return all_pv

    def check_pvc_cache(self, pvc_name, namespace):
        key = pvc_name + ":" + namespace
        return StuckPods.PVC_CACHE.get(key, None)



    def get_unused_volumes(self, all_pods, all_pv):
        used_volumes = []
        unused_volumes = []
        for pod in all_pods:
            pvc_list = pod.pvc_names()
            for pvc in pvc_list:
                pvc_object = self.check_pvc_cache(pvc.pvc_name, pvc.namespace)
                if pvc_object:
                    pv_name = pvc_object.volume
                    used_volumes.append(pv_name)


        for pv in all_pv:
            if pv.pv_name not in used_volumes:
                unused_volumes.append(pv)
        return unused_volumes


if __name__ == "__main__":
    stuckPod = StuckPods()
    stuckPod.run()
