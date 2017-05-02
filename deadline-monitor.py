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
        deadlined_pods = self.get_deadlined_pods()
        if len(deadlined_pods) == 0:
            print "None found. Everything is OK."
            return
        for pod in deadlined_pods:
            self.delete_deadline_pod(pod)

    def get_deadlined_pods(self):
        """
        get pods in DeadlineExceeded state
        """
        output = subprocess.check_output(['oc', 'get', 'pods', '--all-namespaces', '-o', 'json'])
        pod_json = json.loads(output)
        pod_items = pod_json['items']
        pods = []
        for pod in pod_items:
            pod_status = pod['status']
            if pod_status['phase'] == 'Failed' and pod_status.get('reason', '') == 'DeadlineExceeded':
                    pods.append(Pod(pod))
        return pods


    def delete_deadline_pod(self, pod):
        """
        Delete deadline pod
        """
        print "Deleting pod %s in namespace %s" % (pod.pod_name, pod.namespace)
        ret_val = subprocess.check_call(['oc', 'delete', 'pod', pod.pod_name, '-n', pod.namespace])
        if ret_val != 0:
            print "Error deleting pod %s in namespace %s" % (pod.pod_name, pod.namespace)


    def report_pod_pv(self, pod):
        """
        Print out the information about the pod and PV
        """
        pv = self.get_pv_name(pod)
        format_string = "pod: %s\t namespace: %s\t AWS vol-id:%s\t"
        print format_string % (pod.pod_name, pod.namespace, pv)

    def get_pv_name(self, pod):
        pvc_names = pod.pvc_names()
        if len(pvc_names) == 0:
            return "No PVCs on pod"
        pvc_name = pvc_names[0]
        pv_name = pvc_name.get_pv_name()
        output = subprocess.check_output(['oc', 'get', 'pv', pv_name, '-o', 'json'])
        pv_json = json.loads(output)
        if 'awsElasticBlockStore' in pv_json['spec']:
            return pv_json['spec']['awsElasticBlockStore']['volumeID']
        else:
            return "Not an awsElasticBlockStore volume"


class MainApp(object):
    def run(self, argv):
        a = PodAlert()
        parser = OptionParser()

        parser.add_option("-p", "--period", dest="period", help="loop period in SEC seconds; default 180", metavar="SEC", default="180")
        (options, args) = parser.parse_args()
        wait_time = int(options.period)
        while True:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            print "%s *** Checking for pods in DeadlineExceeded state..." % now
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
