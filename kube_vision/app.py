import argparse
from kubernetes import client, config

def main():
    parser = argparse.ArgumentParser(description='Kubernetes Vision CLI')
    # Add your arguments here
    parser.add_argument('--namespace', type=str, default='default', help='Kubernetes namespace to analyze')

    args = parser.parse_args()

    # Load kube config
    config.load_kube_config()

    # Create a Kubernetes API client
    v1 = client.CoreV1Api()

    # List pods in the specified namespace
    print(f"Listing pods in namespace: {args.namespace}")
    pods = v1.list_namespaced_pod(namespace=args.namespace)
    for pod in pods.items:
        print(f"Pod name: {pod.metadata.name}")

if __name__ == '__main__':
    main()
