import subprocess
import json
import datetime
import time
import re
import sys


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


class PodUID(object):
    def run(self, pod_uid):
        all_pods = self.get_all_pods()
        for pod in all_pods:
            if pod.uid == pod_uid:
                print "Pod %s is in %s namespace" % (pod.pod_name, pod.namespace)

    def get_all_pods(self):
        """
        get pods in creating state
        """
        output = subprocess.check_output(['oc', 'get', 'pods', '--all-namespaces', '-o', 'json'])
        pod_json = json.loads(output)
        pod_items = pod_json['items']
        creating_pods = []
        for pod in pod_items:
            creating_pods.append(Pod(pod))
        return creating_pods

a = PodUID()
a.run(sys.argv[1])
