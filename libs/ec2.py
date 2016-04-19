import boto.ec2
import boto.ec2.autoscale

def find_ec2_pending_instances(ghost_app, ghost_env, ghost_role, region, as_group):
    """ Return a list of dict info only for the instances in pending state.

        :param  ghost_app  string: The value for the instance tag "app".
        :param  ghost_env  string: The value for the instance tag "env".
        :param  ghost_role  string: The value for the instance tag "role".
        :param  region  string: The AWS region where the instances are located.
        :return list of dict(ex: [{'id': instance_idXXX, 'private_ip_address': XXX_XXX_XXX_XXX},{...}])
    """
    conn_as = boto.ec2.autoscale.connect_to_region(region)
    conn = boto.ec2.connect_to_region(region)

    # Retrieve pending instances
    pending_instance_filters = {"tag:env": ghost_env, "tag:role": ghost_role, "tag:app": ghost_app, "instance-state-name": "pending"}
    pending_instances = conn.get_only_instances(filters=pending_instance_filters)
    pending_instances_ids = [instance.id for instance in pending_instances]

    autoscale_instances = []
    if as_group:
        autoscale_instances = conn_as.get_all_groups(names=[as_group])[0].instances

    for autoscale_instance in autoscale_instances:
        # Instances in autoscale "Pending" state may not have their tags set yet
        if not autoscale_instance.instance_id in pending_instances_ids and autoscale_instance.lifecycle_state in ['Pending', 'Pending:Wait', 'Pending:Proceed']:
            pending_instances.append(conn.get_only_instances(instance_ids=[autoscale_instance.instance_id])[0])

    hosts = []
    for instance in pending_instances:
        hosts.append({'id': instance.id, 'private_ip_address': instance.private_ip_address})

    return hosts

def find_ec2_running_instances(ghost_app, ghost_env, ghost_role, region):
    """ Return a list of dict info only for the running instances.

        :param  ghost_app  string: The value for the instance tag "app".
        :param  ghost_env  string: The value for the instance tag "env".
        :param  ghost_role  string: The value for the instance tag "role".
        :param  region  string: The AWS region where the instances are located.
        :return list of dict(ex: [{'id': instance_idXXX, 'private_ip_address': XXX_XXX_XXX_XXX},{...}])
    """
    conn_as = boto.ec2.autoscale.connect_to_region(region)
    conn = boto.ec2.connect_to_region(region)

    # Retrieve running instances
    running_instance_filters = {"tag:env": ghost_env, "tag:role": ghost_role, "tag:app": ghost_app, "instance-state-name": "running"}
    running_instances = conn.get_only_instances(filters=running_instance_filters)

    hosts = []
    for instance in running_instances:
        # Instances in autoscale "Terminating:*" states are still "running" but no longer in the Load Balancer
        autoscale_instances = conn_as.get_all_autoscaling_instances(instance_ids=[instance.id])
        if not autoscale_instances or not autoscale_instances[0].lifecycle_state in ['Terminating', 'Terminating:Wait', 'Terminating:Proceed']:
            hosts.append({'id': instance.id, 'private_ip_address': instance.private_ip_address})

    return hosts
