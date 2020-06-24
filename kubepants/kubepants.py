from kubernetes import client, config, watch, stream
import sys
import os
import uuid
import requests
import logging
import time
import threading
import random

from types import SimpleNamespace

class KubePants:
    """
    The idea here is to set up an end-to-end test webapp in kubernetes, then
    run some tests against it to make sure it keeps running when things go wrong.
    """
    def __init__(self,**kwargs):
        from kubepants.specs import deploy, pvc, svc
        kubeconfig = kwargs.get("kubeconfig",os.environ.get("KUBECONFIG",None))
        self._genval = kwargs.get("genval",str(uuid.uuid4()))
        self._namespace = kwargs.get("namespace","default")

        config.load_kube_config(kubeconfig)
        client_config = client.Configuration()
        client_config.assert_hostname = False
        api_client = client.api_client.ApiClient(configuration=client_config)
        self.pod_client = client.CoreV1Api(api_client)
        self.app_client = client.AppsV1Api(api_client)
        self._pod = ""
        self._node = ""
        self._nodes = []
        self._ip = ""
        self._specs = SimpleNamespace(
            deploy=deploy,
            pvc=pvc,
            svc=svc
        )

    @property
    def pod(self):
        return self._pod

    @property
    def node(self):
        return self._node

    @property
    def nodes(self):
        return self._nodes

    @property
    def ip(self):
        return self._ip

    @property
    def genval(self):
        return self._genval

    @property
    def specs(self):
        return self._specs

    @property
    def namespace(self):
        return self._namespace

    @property
    def svc_name(self):
        return self.specs.svc["metadata"]["name"]

    @property
    def deploy_name(self):
        return self.specs.deploy["metadata"]["name"]

    @property
    def pvc_name(self):
        return self.specs.pvc["metadata"]["name"]

    @property
    def new_node(self):
        return random.choice([x for x in self.nodes if x != self.node ])

    def setup(self):
        logging.info("Doing initial setup")

        logging.info("Creating pvc")
        api_response = self.pod_client.create_namespaced_persistent_volume_claim(self.namespace, body=self.specs.pvc)

        logging.info("Creating pod")
        api_response = self.app_client.create_namespaced_deployment(self.namespace, body=self.specs.deploy)

        logging.info("creating service")
        api_response = self.pod_client.create_namespaced_service(self.namespace, body=self.specs.svc)

        time.sleep(5)

        _nodes = self.pod_client.list_node()
        self._nodes = [ x.metadata.name for x in _nodes.items ]

        self.get_info()

    def get_info(self):
        #_pod = app_client.read_namespaced_deployment("test-deploy","default")
        _pod = self.pod_client.list_namespaced_pod(self.namespace,label_selector="app=test")
        self._pod = [ x.metadata.name for x in _pod.items][0]
        _info = self.pod_client.read_namespaced_pod(self.pod, self.namespace)
        _svc = self.pod_client.read_namespaced_service(self.svc_name, self.namespace)
        self._node = str(_info.spec.node_name)
        self._ip = _svc.status.load_balancer.ingress[0].ip

    def cleanup(self):
        logging.info("Cleaning up")

        logging.info("Deleting the deployment")
        try:
            self.app_client.delete_namespaced_deployment(self.deploy_name, self.namespace)
        except Exception as e:
            logging.debug(sys.exc_info()[0])
            logging.debug(e)
        
        logging.info("Deleting the svc")
        try:
            self.pod_client.delete_namespaced_service(self.svc_name, self.namespace)
        except Exception as e:
            logging.debug(sys.exc_info()[0])
            logging.debug(e)
        
        logging.info("Deleting the pvc")
        try:
            self.pod_client.delete_namespaced_persistent_volume_claim(self.pvc_name, self.namespace, grace_period_seconds=0, propagation_policy='Foreground')
            time.sleep(5)
        except Exception as e:
            logging.debug(sys.exc_info()[0])
            logging.debug(e)

    def delete_pod(self):
        logging.info("deleting a pod to see what happens")
        self.pod_client.delete_namespaced_pod(self.pod,self.namespace)
        time.sleep(10)

        self.get_info()

    def write_to_pod(self):
        logging.info(f"Writing {self.genval} to our pvc")

        exec_command = ["/bin/bash","-c",f"echo {self.genval} > /usr/share/nginx/html/index.html"]
        stream.stream(self.pod_client.connect_get_namespaced_pod_exec, self.pod, self.namespace,command=exec_command, stderr=True, stdin=False, stdout=True, tty=False)

    def move_pod(self):

        new_node = self.new_node

        logging.info(f"Moving pod from {self.node} to {new_node}")

        patch_spec = self.specs.deploy

        patch_spec["spec"]["template"]["spec"]["nodeName"] = new_node

        self.app_client.patch_namespaced_deployment(self.specs.deploy["metadata"]["name"], self.namespace, body=patch_spec)

        # patch the deployment, which creates a new pod and deletes the old one.
        # wait for that to finish
        time.sleep(10)

        self.get_info()

    def service_monitor(self):
        logging.info("starting service monitor")
        self.thread = threading.Thread(target=self.t_check, args=(self.ip,self.genval))
        self.thread.daemon = True
        self.thread.start()

    def t_check(self,ip,expected_value,once=False):
        _fail_timer = 0
        while True:
            try:
                res = requests.get(f"http://{ip}")
                got_value = str(res.text).strip()
                assert got_value == expected_value, "Values didn't match"
                logging.debug(f"Got {got_value} expected {expected_value}")
            except Exception as e:
                logging.info(sys.exc_info()[0])
                logging.info(e)
                _fail_timer += 1
            else:
                logging.debug("Successful svc ping")
                if _fail_timer:
                    logging.info(f"fail timer lasted {_fail_timer} seconds")
                    _fail_timer = 0
            if once:
                break
            time.sleep(1)

