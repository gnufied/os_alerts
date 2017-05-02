#!/usr/bin/python

import subprocess
import json
import datetime
import time
import re
import traceback
import sys
from optparse import OptionParser

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

    def pvc_names(self):
        pvc_claims = []
        for volume in self.pod_data['spec']['volumes']:
            if 'persistentVolumeClaim' in volume:
                pvc_claims.append(PVC(volume['persistentVolumeClaim']['claimName'], self.namespace))
        return pvc_claims


class PodAlert(object):
    def run(self):
        completed_pods = self.get_completed_pods()
        if len(completed_pods) == 0:
            print "None found. Everything is OK."
            return
        for pod in completed_pods:
            self.delete_completed_pod(pod)

    def get_completed_pods(self):
        """
        get pods in Completed state
        """
        output = subprocess.check_output(['oc', 'get', 'pods', '--all-namespaces', '-o', 'json'])
        pod_json = json.loads(output)
        pod_items = pod_json['items']
        pods = []
        for pod in pod_items:
            pod_status = pod['status']
            if pod_status['phase'] == 'Succeeded' and self.check_terminated_containers(pod_status):
                pods.append(Pod(pod))
        return pods

    def check_terminated_containers(self, pod_status):
        pcs = pod_status.get('containerStatuses', [])
        container_states = []
        for csd in pcs:
            cs = csd.get('state', {}).get('terminated', {}).get('reason', '')
            container_states.append(cs)
        terminated_containers = [cs == 'Completed' for cs in container_states]
        return len(terminated_containers) == len(pcs)


    def delete_completed_pod(self, pod):
        """
        Delete completed pod
        """
        pvc_names = pod.pvc_names()
        if len(pvc_names) == 0:
            return

        print "Deleting pod %s in namespace %s" % (pod.pod_name, pod.namespace)
        ret_val = subprocess.check_call(['oc', 'delete', 'pod', pod.pod_name, '-n', pod.namespace])
        if ret_val != 0:
            print "Error deleting pod %s in namespace %s" % (pod.pod_name, pod.namespace)



class MainApp(object):
    def run(self, argv):
        a = PodAlert()
        parser = OptionParser()

        parser.add_option("-p", "--period", dest="period", help="loop period in SEC seconds; default 180", metavar="SEC", default="180")
        (options, args) = parser.parse_args()
        wait_time = int(options.period)
        while True:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            print "%s *** Checking for pods in Completed state..." % now
            a.run()
            time.sleep(wait_time)


if __name__ == '__main__':
    app = MainApp();
    try:
        app.run(sys.argv[1:])
        sys.exit(0)
    except KeyboardInterrupt:
        print "Quitting"
    except Exception as e:
        traceback.print_exc()
        sys.exit(e)
