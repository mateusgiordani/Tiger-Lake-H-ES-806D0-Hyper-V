#!/usr/bin/env python3
"""Compare two collect_tgl_vmx_msrs_linux.py evidence directories (ON vs OFF)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PINBASED = {0: "external_int_exiting", 2: "nmi_exiting", 3: "virtual_nmis",
            5: "activate_vnmi", 6: "process_posted_interrupts"}

PROCBASED_PRIMARY = {
    2: "int_window_exiting", 3: "tsc_offsetting", 7: "hlt_exiting",
    9: "invlpg_exiting", 10: "mwait_exiting", 11: "rdpmc_exiting",
    12: "rdtsc_exiting", 15: "cr3_load_exiting", 16: "cr3_store_exiting",
    19: "cr8_load_exiting", 20: "cr8_store_exiting", 21: "use_tpr_shadow",
    22: "nmi_window_exiting", 23: "mov_dr_exiting", 24: "uncond_io_exiting",
    25: "use_io_bitmaps", 27: "monitor_trap_flag", 28: "use_msr_bitmaps",
    30: "monitor_exiting", 31: "pause_exiting", 32: "activate_secondary_ctls",
}

ENTRY = {2: "load_debug_ctls", 9: "ia32e_guest", 10: "entry_to_smm",
         11: "deact_dual_monitor", 13: "load_perf_global_ctrl",
         14: "load_pat", 15: "load_efer"}

EXIT = {2: "host_addr_space_64", 9: "ack_intr_on_exit", 10: "save_efer",
        11: "load_efer", 12: "save_perf_global_ctrl",
        13: "load_perf_global_ctrl", 14: "save_pat", 15: "load_pat"}


def hx(s): return int(str(s), 16)


def names(v_may1, table):
    return sorted(n for b, n in table.items() if v_may1 & (1 << b))


def load(d):
    return json.loads((Path(d) / "tgl-vmx-msrs.json").read_text())


def cpu0(data): return data["per_cpu"]["0"]


def msr_val(entry):
    return hx(entry["value"]) if isinstance(entry, dict) and "value" in entry else None


def summarize(tag, data):
    print(f"===== {tag} =====")
    print("kernel:", data["kernel"])
    print("cpuinfo:", data["cpuinfo"])
    print("online:", data["online_cpus"])
    groups = data["identical_msr_groups"]
    print("identical_msr_groups:", groups)
    if len(groups) == 1 and len(groups[0]) == len(data["online_cpus"]):
        print("  -> ALL LPs IDENTICAL")
    else:
        print("  -> !! LP GROUPS DIFFER !!")
    errs = data["errors"]
    print("errors:", len(errs))
    for e in errs[:10]:
        print("   ", e)

    c0 = cpu0(data)
    fc = c0["IA32_FEATURE_CONTROL"]["feature_control"]
    print(f"FEATURE_CONTROL: locked={fc['locked']} vmx_off_smx={fc['vmx_outside_smx']} "
          f"senter_glob={fc['senter_global_enable']} sgx={fc['sgx_global_enable']}")
    ab = c0["IA32_APIC_BASE"]["apic"]
    print(f"APIC_BASE(cpu0): bsp={ab['bsp']} x2apic={ab['x2apic_enabled']} "
          f"global_en={ab['apic_global_enable']} base={ab['base']}")
    mc = msr_val(c0["IA32_BIOS_SIGN_ID"])
    print(f"microcode(BIOS_SIGN_ID>>32): 0x{(mc or 0) >> 32:X}")

    basic = c0["IA32_VMX_BASIC"]
    vb = basic["vmx_basic"]
    print(f"VMX_BASIC: rev={vb['vmcs_revision_id']} region={vb['vmcs_region_bytes']}B "
          f"phys32={vb['physical_address_width_32_only']} memtype={vb['memory_type']} "
          f"true_ctls={vb['true_controls']}")

    def may(name):
        return hx(c0[name]["control"]["may_be_1"])

    def must(name):
        return hx(c0[name]["control"]["must_be_1"])

    pb2 = may("IA32_VMX_PROCBASED_CTLS2")
    print("PINBASED may-enable:", names(may("IA32_VMX_PINBASED_CTLS"), PINBASED))
    print("PROCBASED may-enable (key):",
          [n for n in names(may("IA32_VMX_PROCBASED_CTLS"), PROCBASED_PRIMARY)])
    print("PROCBASED2 may-enable:", c0["IA32_VMX_PROCBASED_CTLS2"]["may_enable"])
    print("ENTRY may-enable:", names(may("IA32_VMX_ENTRY_CTLS"), ENTRY))
    print("EXIT may-enable:", names(may("IA32_VMX_EXIT_CTLS"), EXIT))

    ev = c0["IA32_VMX_EPT_VPID_CAP"]["capabilities"]
    print("EPT_VPID_CAP features:", ev)

    misc = msr_val(c0["IA32_VMX_MISC"])
    if misc is not None:
        print(f"VMX_MISC: preempt_rate_bits={misc & 0x1F} "
              f"cr3_targets={(misc >> 16) & 0x1FF} "
              f"eptp_switch_via_vmfunc={'yes' if misc & (1 << 33) else 'no'}")
    return data


def cross_lp_diff(data, tag):
    bad = []
    cpus = [str(c) for c in data["online_cpus"]]
    ref = cpus[0]
    for ref_c in cpus:
        pass
    ref_c = cpus[0]
    for name in data["per_cpu"][ref_c]:
        base = json.dumps(data["per_cpu"][ref_c][name], sort_keys=True)
        for c in cpus[1:]:
            other = json.dumps(data["per_cpu"][c].get(name), sort_keys=True)
            if base != other and name != "IA32_TIME_STAMP_COUNTER":
                if name == "IA32_APIC_BASE":
                    a, b = data["per_cpu"][ref_c][name], data["per_cpu"][c][name]
                    if msr_val(a) is not None and (msr_val(a) & ~(1 << 8)) == (msr_val(b) & ~(1 << 8)):
                        continue
                bad.append((name, ref_c, c))
    print(f"[{tag}] cross-LP mismatches beyond TSC/APIC-BSP-bit:", bad or "none")


def run_diff(on, off):
    print("\n===== ON vs OFF (cpu0) =====")
    changed = {}
    keys = set(cpu0(on)) | set(cpu0(off))
    for k in sorted(keys):
        a, b = cpu0(on).get(k), cpu0(off).get(k)
        ja, jb = json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True)
        if ja != jb:
            changed[k] = (a, b)
            va, vb = msr_val(a), msr_val(b)
            if va is not None and vb is not None and va != vb:
                print(f"{k}: 0x{va:016X} -> 0x{vb:016X}")
            elif isinstance(a, dict) and "feature_control" in a:
                print(f"{k}: {a['feature_control']}")
                print(f"      -> {b['feature_control']}")
            else:
                sa = json.dumps(a)[:160]
                sb = json.dumps(b)[:160]
                print(f"{k}: {sa}")
                print(f"      -> {sb}")
    print("changed MSRs count:", len(changed))
    # microcode both runs
    for tag, d in (("ON", on), ("OFF", off)):
        mc = msr_val(cpu0(d)["IA32_BIOS_SIGN_ID"])
        print(f"microcode {tag}: 0x{(mc or 0) >> 32:X}")


def cpuid_flags(dirpath, tag):
    txt = (Path(dirpath) / "cpuinfo.txt").read_text(errors="replace")
    first = txt.split("\n\n")[0]
    flags_line = ""
    for line in first.splitlines():
        if line.startswith("flags"):
            flags_line = line.split(":", 1)[1]
    interesting = ["vmx", "avx512f", "avx512vl", "vp2intersect", "avx512bw",
                   "avx512cd", "avx512dq", "avx512ifma", "avx512vbmi",
                   "avx512_vpopcntdq", "hypervisor", "pdcm", "tme"]
    found = [f for f in interesting if f in flags_line.split()]
    print(f"[{tag}] notable cpuinfo flags:", found)


def topology(dirpath, tag):
    lines = (Path(dirpath) / "cpuinfo.txt").read_text(errors="replace").splitlines()
    entries = {}
    cur = {}
    for line in lines:
        if not line.strip():
            if cur:
                entries[cur.get("processor")] = cur
            cur = {}
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            cur[k.strip()] = v.strip()
    if cur:
        entries[cur.get("processor")] = cur
    rows = [(p, e.get("apicid"), e.get("core id"), e.get("core type"),
             e.get("microcode")) for p, e in sorted(entries.items(), key=lambda kv: int(kv[0]))]
    print(f"[{tag}] per-LP apicid/core/type/microcode:")
    for r in rows:
        print("   ", r)


def main():
    on_d, off_d = sys.argv[1], sys.argv[2]
    on, off = load(on_d), load(off_d)
    summarize("VMX-ON (estado em que o Hyper-V falha)", on)
    cross_lp_diff(on, "ON")
    summarize("VMX-OFF", off)
    cross_lp_diff(off, "OFF")
    run_diff(on, off)
    print()
    cpuid_flags(on_d, "ON")
    cpuid_flags(off_d, "OFF")
    print()
    topology(on_d, "ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
