"""
host_task_states
"""
DETECTING = 'detecting'
COLLECTING = 'collecting'
MIGRATING_OUT = 'migrating_out'
MIGRATING_IN = 'migrating_in'
DO_NOTING = 'do_nothing'

"""
host_running_states
"""
NORMAL_POWER = 'normal_power'
LOW_POWER = 'low_power'

"""
host_load_states
"""
NORMALLOAD = 'normalload'
OVERLOAD = 'overload'
UNDERLOAD = 'underload'

"""
vm_task_state
"""
VM_MIGRATING = 'vm_migrating'
VM_NORMAL = 'vm_normal'

"""
migration task state
"""
MIGRATION_SUCCESS = 'migration_success'
MIGRATION_FAILURE = 'migration_failure'
