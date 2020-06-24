
deploy = {
    "metadata": { "name": "test-deploy", "labels": { "app": "test" }},
    "spec": {
        "replicas": 1,
        "selector": { "matchLabels": { "app": "test" }},
        "template": {
            "metadata": { "name": "test-pod", "labels": { "app": "test" }},
            "spec": {
                "restart_policy": "Never",
                "containers": [
                    {   
                        "name": "test-pod",
                        "image": "nginx:latest",
                        "volumeMounts": [{ "name": "test-vol", "mountPath": "/usr/share/nginx/html", "readOnly": False }]
                    }
                ],
                "volumes": [{ "name": "test-vol", "persistentVolumeClaim": { "claimName": "test-pvc" }}]
            },
        }
    }
}

pvc = {
    "metadata": { "name": "test-pvc" },
    "spec": {
        "storageClassName": "managed-nfs-storage",
        "resources": { "requests": { "storage": "1Mi" }},
        "accessModes": [ "ReadWriteMany", ],
        "volumeMode": "Filesystem",
    },
}

svc = {
    "metadata": { "name": "test-svc", "labels": { "app": "test" }},
    "spec": {
        "type": "LoadBalancer",
        "externalTrafficPolicy": "Cluster",
        "sessionAffinity": None,
        "selector": {
            "app": "test",
        },
        "ports": [{
            "port": 80,
            "targetPort": 80,
            "protocol": "TCP",
        }],
    },
}

