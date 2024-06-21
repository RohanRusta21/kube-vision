# kube_vision/app.py

import argparse
from kubernetes import client, config

def main():
    parser = argparse.ArgumentParser(description='Kubernetes Vision CLI')

    # Add the specified flags
    parser.add_argument('--as-user', type=str, help='User to impersonate command with')
    parser.add_argument('--as-group', type=str, help='Group to impersonate command with')
    parser.add_argument('-c', '--containers', action='store_true', help='Include containers in output')
    parser.add_argument('--context', type=str, help='Context to use for Kubernetes config')
    parser.add_argument('--kubeconfig', type=str, help='Kubeconfig file to use for Kubernetes config')
    parser.add_argument('-n', '--namespace', type=str, help='Only include pods from this namespace')
    parser.add_argument('--namespace-labels', type=str, help='Labels to filter namespaces with')
    parser.add_argument('--no-taint', action='store_true', help='Exclude nodes with taints')
    parser.add_argument('--node-labels', type=str, help='Labels to filter nodes with')
    parser.add_argument('-o', '--output', type=str, default='table', choices=['table', 'json', 'yaml', 'csv', 'tsv'], help='Output format for information')
    parser.add_argument('-a', '--available', action='store_true', help='Include quantity available instead of percentage used (ignored with csv or tsv output types)')
    parser.add_argument('-t', '--node-taints', type=str, help='Taints to filter nodes with')
    parser.add_argument('-l', '--pod-labels', type=str, help='Labels to filter pods with')
    parser.add_argument('-p', '--pods', action='store_true', help='Include pods in output')
    parser.add_argument('--sort', type=str, default='name', choices=[
        'cpu.util', 'cpu.request', 'cpu.limit', 'mem.util', 'mem.request', 'mem.limit',
        'cpu.util.percentage', 'cpu.request.percentage', 'cpu.limit.percentage',
        'mem.util.percentage', 'mem.request.percentage', 'mem.limit.percentage', 'name'
    ], help='Attribute to sort results by')
    parser.add_argument('-u', '--util', action='store_true', help='Include resource utilization in output')
    parser.add_argument('--pod-count', action='store_true', help='Include pod counts for each of the nodes and the whole cluster')

    args = parser.parse_args()

    # Load kube config
    if args.kubeconfig:
        config.load_kube_config(config_file=args.kubeconfig, context=args.context)
    else:
        config.load_kube_config(context=args.context)

    # Handle impersonation
    if args.as_user or args.as_group:
        configuration = client.Configuration()
        if args.as_user:
            configuration.impersonate = {'user': args.as_user}
        if args.as_group:
            configuration.impersonate['group'] = args.as_group
        client.Configuration.set_default(configuration)

    # Create Kubernetes API clients
    v1 = client.CoreV1Api()
    v1_apps = client.AppsV1Api()

    # Define a function to parse resources
    def parse_resource(resource):
        if resource.endswith('m'):
            return int(resource[:-1])
        if resource.endswith('Mi'):
            return int(resource[:-2])
        if resource.endswith('Gi'):
            return int(resource[:-2]) * 1024
        return int(resource)

    # Fetch nodes and filter based on labels and taints
    nodes = v1.list_node().items
    if args.node_labels:
        node_labels = dict(label.split('=') for label in args.node_labels.split(','))
        nodes = [node for node in nodes if all(
            node.metadata.labels.get(k) == v for k, v in node_labels.items())]
    if args.no_taint:
        nodes = [node for node in nodes if not node.spec.taints]
    if args.node_taints:
        node_taints = args.node_taints.split(',')
        nodes = [node for node in nodes if all(
            taint.key in node_taints for taint in node.spec.taints or [])]

    # Fetch namespaces and filter based on labels
    namespaces = [args.namespace] if args.namespace else [ns.metadata.name for ns in v1.list_namespace().items]
    if args.namespace_labels:
        namespace_labels = dict(label.split('=') for label in args.namespace_labels.split(','))
        namespaces = [ns for ns in namespaces if all(
            v1.read_namespace(ns).metadata.labels.get(k) == v for k, v in namespace_labels.items())]

    # Collect and display the resource usage information
    header_format = "{:<18}{:<15}{:<25}{:<15}{:<15}{:<20}{:<15}"
    row_format = "{:<18}{:<15}{:<25}{:<15}{:<15}{:<20}{:<15}"
    print(header_format.format("NODE", "NAMESPACE", "POD", "CPU REQUESTS", "CPU LIMITS", "MEMORY REQUESTS", "MEMORY LIMITS"))

    for node in nodes:
        node_name = node.metadata.name

        # Initialize totals
        total_cpu_requests = 0
        total_cpu_limits = 0
        total_memory_requests = 0
        total_memory_limits = 0
        total_pod_count = 0

        for ns in namespaces:
            # Retrieve pods in the namespace
            pods = v1.list_namespaced_pod(ns, field_selector=f"spec.nodeName={node_name}").items

            for pod in pods:
                pod_name = pod.metadata.name
                namespace = pod.metadata.namespace

                # Initialize pod totals
                pod_cpu_requests = 0
                pod_cpu_limits = 0
                pod_memory_requests = 0
                pod_memory_limits = 0

                for container in pod.spec.containers:
                    resources = container.resources

                    if resources.requests:
                        pod_cpu_requests += parse_resource(resources.requests.get('cpu', '0'))
                        pod_memory_requests += parse_resource(resources.requests.get('memory', '0Mi'))

                    if resources.limits:
                        pod_cpu_limits += parse_resource(resources.limits.get('cpu', '0'))
                        pod_memory_limits += parse_resource(resources.limits.get('memory', '0Mi'))

                total_cpu_requests += pod_cpu_requests
                total_cpu_limits += pod_cpu_limits
                total_memory_requests += pod_memory_requests
                total_memory_limits += pod_memory_limits
                total_pod_count += 1

                print(row_format.format(
                    node_name, namespace, pod_name,
                    f"{pod_cpu_requests}m ({pod_cpu_requests // 10}%)",
                    f"{pod_cpu_limits}m ({pod_cpu_limits // 10}%)",
                    f"{pod_memory_requests}Mi ({pod_memory_requests // 1024}%)",
                    f"{pod_memory_limits}Mi ({pod_memory_limits // 1024}%)"
                ))

        # Print totals for the node
        print(row_format.format(
            node_name, '*', '*',
            f"{total_cpu_requests}m ({total_cpu_requests // 10}%)",
            f"{total_cpu_limits}m ({total_cpu_limits // 10}%)",
            f"{total_memory_requests}Mi ({total_memory_requests // 1024}%)",
            f"{total_memory_limits}Mi ({total_memory_limits // 1024}%)"
        ))

        if args.pod_count:
            print(f"Total pod count for node {node_name}: {total_pod_count}")

if __name__ == '__main__':
    main()
