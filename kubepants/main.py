import sys
import logging
import random

from kubepants.kubepants import KubePants

logging.basicConfig(level=logging.INFO)

def main():
    kk = KubePants()

    # cleanup any old tests, just in case
    kk.cleanup()

    # create the deployment, svc and pvc
    kk.setup()

    # write a random value to the pod
    kk.write_to_pod()

    # poll the pod for the random value
    # in the background while we perform tests
    kk.service_monitor()

    # move our pod to a new (random) node and see if we lose
    # any connectivity from our svc
    kk.move_pod()

    # terminate the pod and see if we lose connectivity
    # with one replica, this WILL cause downtime
    kk.delete_pod()

    # remove the deployment, svc and pvc
    kk.cleanup()

    sys.exit()

if __name__ == '__main__':
    sys.exit(main())
