"""Retry creating ONE Oracle Always Free A1 VM (2 OCPU / 12 GB). All IDs come from secrets.
Logs never print OCIDs, IPs or keys."""
import os, sys, time, random, oci

E = os.environ
cfg = {"user": E["OCI_USER"], "tenancy": E["OCI_TENANCY"], "fingerprint": E["OCI_FINGERPRINT"],
       "region": E["OCI_REGION"], "key_content": E["OCI_KEY"]}
oci.config.validate_config(cfg)
COMP, AD, SUBNET, IMAGE, SSH = E["OCI_COMPARTMENT"], E["OCI_AD"], E["OCI_SUBNET"], E["OCI_IMAGE"], E["SSH_PUBKEY"]
BUDGET = float(E.get("RUN_SECONDS", "10"))   # keep each job under ~1 billed minute
GAP = float(E.get("GAP_SECONDS", "20"))
SHAPE = "VM.Standard.A1.Flex"
co = oci.core.ComputeClient(cfg, retry_strategy=oci.retry.NoneRetryStrategy(), timeout=(15, 60))
m = oci.core.models

def log(s): print(time.strftime("%H:%M:%S UTC ", time.gmtime()) + s, flush=True)
def out(k, v):
    with open(E.get("GITHUB_OUTPUT", "/dev/null"), "a") as f: f.write(f"{k}={v}\n")

def active_a1():
    xs = oci.pagination.list_call_get_all_results(co.list_instances, compartment_id=COMP).data
    return [x for x in xs if x.shape == SHAPE and x.lifecycle_state not in ("TERMINATED", "TERMINATING")]

def done(inst):
    deadline = time.time() + 900
    while inst.lifecycle_state != "RUNNING" and time.time() < deadline:
        if inst.lifecycle_state in ("TERMINATED", "TERMINATING"): break
        time.sleep(15); inst = co.get_instance(inst.id).data
    log("A1 instance present, state=" + inst.lifecycle_state)
    out("created", "true"); sys.exit(0)

start = time.time()
attempt = 0
while True:
    found = active_a1()                      # check before EVERY launch
    if found:
        if len(found) > 1: log("WARNING: more than one A1 instance exists - manual review needed")
        done(found[0])
    attempt += 1
    details = m.LaunchInstanceDetails(
        compartment_id=COMP, availability_domain=AD, display_name="free-a1", shape=SHAPE,
        shape_config=m.LaunchInstanceShapeConfigDetails(ocpus=2, memory_in_gbs=12),  # Always Free max - never more
        source_details=m.InstanceSourceViaImageDetails(source_type="image", image_id=IMAGE, boot_volume_size_in_gbs=50),
        create_vnic_details=m.CreateVnicDetails(subnet_id=SUBNET, assign_public_ip=True, hostname_label="free-a1"),
        metadata={"ssh_authorized_keys": SSH.strip()},
        instance_options=m.InstanceOptions(are_legacy_imds_endpoints_disabled=True))
    try:
        log(f"Attempt {attempt}: launching A1 2 OCPU / 12 GB")
        inst = co.launch_instance(details).data
        log("Launch accepted")
        done(inst)
    except oci.exceptions.ServiceError as e:
        log(f"Launch error: status={e.status} code={e.code} message={e.message}")
        if e.status == 429: log("Rate limited - stop this run, next scheduled run retries"); break
        if e.status in (500, 503) and "capacity" in (e.message or "").lower(): pass
        elif e.status >= 500:
            # uncertain outcome: re-check inventory before anything else
            time.sleep(10)
            if active_a1(): continue
        else:
            log("Non-capacity error - failing so it is visible"); sys.exit(1)
    if time.time() - start + GAP > BUDGET: break
    time.sleep(GAP + random.uniform(0, 5))
log("No capacity this run")
