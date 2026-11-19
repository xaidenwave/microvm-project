# MicroVMs vs Traditional VMs: Boot Time, Overhead and Memory Density on KVM

📄 **Paper:** [PDF](paper/MicroVM_Research_Paper_Group3.pdf) · [LaTeX source](paper/)

A controlled experiment comparing how fast and how cheaply different kinds of
isolated environments start on the same KVM hypervisor: a traditional VM,
QEMU's `microvm` machine type, AWS Firecracker, and a Podman container.

The two microVM tiers boot the **identical guest kernel and root filesystem**,
so differences between them come from the VMM alone. Boot time is measured both
on the host (wall-clock) and inside the guest (kernel log timestamps), which
splits it into guest time and VMM overhead.

**Group 3 · Cloud Computing (ITITE503) · IT-1 · Netaji Subhas University of Technology**
Sanyam Budwal (2024UIT3057) · Aashi Bhatt (2024UIT3014) · Sohaib (2024UIT3066)

---

## Tiers compared

| Tier | VMM / runtime | Machine | Guest | Resources |
|---|---|---|---|---|
| T1 Traditional VM | QEMU 10.2.2 | `q35` + SeaBIOS + GRUB | Fedora 44 Cloud (systemd) | 1 vCPU, 1024 MB |
| T2 QEMU microvm | QEMU 10.2.2 | `microvm,pit=off,pic=off` | Linux 6.1 (Firecracker CI kernel) + Alpine rootfs | 1 vCPU, 128 MB |
| T3 Firecracker | Firecracker v1.17.0 | Firecracker default | Same kernel and rootfs as T2 | 1 vCPU, 128 MB |
| T4 Container | Podman | n/a (shares host kernel) | Alpine container | n/a |

T3 was measured twice: **default**, and **tuned** with
`i8042.noaux i8042.nomux i8042.nopnp i8042.dumbkbd` (skips a 0.48 s keyboard
controller probe in the guest).

## Key results

All measurements on one machine: Intel Core i5-7500 (4 cores), 15.4 GiB RAM,
Fedora 44, Linux 7.2.13, CPU governor set to `performance`.

**Boot latency (B1)**, quiet console, read-only rootfs:

| Tier | Mean | Std dev | Runs |
|---|---|---|---|
| T1 Traditional VM (time until `BOOTED`) | 12.55 s | 0.58 s | 5 |
| T2 QEMU microvm | 162.5 ms | 5.4 ms | 30 |
| T3 Firecracker default | 631.0 ms | 3.4 ms | 30 |
| T3 Firecracker tuned | 118.6 ms | 3.4 ms | 30 |
| T4 Podman container | 135.4 ms | 22.5 ms | 30 |

**Guest vs VMM time (B2)**: guest kernel reached `/init` in 42.5 ms (T2) and
49.1 ms (T3); VMM-side overhead was 119.9 ms (T2) and 69.5 ms (T3), 42% lower.

**Host memory per running instance (B3)**: T1 ~495 MB, T2 ~114 MB,
T3 ~47 MB, T4 ~2.4 MB (container process + conmon, excluding the shared host kernel).

**Density with KSM, 20 identical VMs (B4)**: QEMU microvm dropped from ~70 to
~44 MB per VM (515 MB saved in total, `ksmd` at 6.4% CPU). Firecracker stayed at
~45 MB per VM with 0 pages merged, because it does not mark guest memory as mergeable.

**Serial console cost**: printing boot messages added 255 ms (T2) and 223 ms (T3).

Raw outputs are in [`logs/`](logs/), charts in [`charts/`](charts/), and
terminal screenshots in [`screenshots/`](screenshots/).

## Repository contents

```
run_t1.sh             Launch the traditional VM (QEMU q35) from a qcow2 image
run_t2.sh             Launch the QEMU microvm; extra args go to the kernel command line
run_t3.sh             Launch Firecracker; extra args go to the kernel command line
bench_t1.sh           5 T1 boots: time until BOOTED, systemd-analyze, total time
bench_b2.sh           10 boots per microVM: guest timestamp of "Run /init"
bench_b4.sh           20-VM density test with and without KSM (t2 or t3)
boot-report.service   systemd unit added to the T1 benchmark overlay
guest/init            The microVM guest's init script
plot.py               Generates the charts from logs/
logs/                 Raw benchmark results (hyperfine JSON/Markdown, CSV, text)
charts/               Generated charts
screenshots/          Terminal screenshots of every step
presentation/         Project presentation
```

Large files are not included: the guest kernel, root filesystem image,
Fedora Cloud image and Firecracker binary are downloaded or rebuilt with the
steps below.

## Reproducing the experiment

Requires a Linux host with KVM (tested on Fedora 44). Run everything from the
repository folder.

### 1. Install tools and check KVM

```bash
sudo dnf install -y @virtualization hyperfine libguestfs-tools sysstat \
  python3-pandas python3-matplotlib kernel-tools podman
sudo usermod -aG kvm $USER        # log out and back in
virt-host-validate qemu            # hardware virtualization and /dev/kvm must PASS
```

### 2. Download Firecracker

```bash
ARCH="$(uname -m)"
release_url="https://github.com/firecracker-microvm/firecracker/releases"
latest=$(basename $(curl -fsSLI -o /dev/null -w %{url_effective} ${release_url}/latest))
curl -L ${release_url}/download/${latest}/firecracker-${latest}-${ARCH}.tgz | tar -xz
mv release-${latest}-${ARCH}/firecracker-${latest}-${ARCH} ./firecracker
```

This study used v1.17.0.

### 3. Get the guest kernel (Firecracker CI build)

```bash
mkdir -p images logs charts
for v in 17 16 15 14 13 12 11 10; do
  keys=$(curl -s "http://spec.ccfc.min.s3.amazonaws.com/?prefix=firecracker-ci/v1.$v/${ARCH}/vmlinux-&list-type=2" \
    | grep -oP '(?<=<Key>)[^<]+' | grep -E 'vmlinux-[0-9.]+$')
  [ -n "$keys" ] && break
done
KEY=$(echo "$keys" | sort -V | tail -1)
curl -fL -o images/vmlinux "https://s3.amazonaws.com/spec.ccfc.min/${KEY}"
```

This study used Linux 6.1.155.

### 4. Build the Alpine root filesystem

```bash
ALPINE=$(curl -s https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/x86_64/latest-releases.yaml \
  | grep -oP 'alpine-minirootfs-[0-9.]+-x86_64\.tar\.gz' | head -1)
curl -fLO "https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/x86_64/${ALPINE}"
mkdir rootfs
sudo tar -xzpf "$ALPINE" -C rootfs
sudo mknod -m 600 rootfs/dev/console c 5 1
sudo mknod -m 666 rootfs/dev/null c 1 3
sudo cp guest/init rootfs/init && sudo chmod +x rootfs/init
truncate -s 64M images/rootfs.ext4
sudo mkfs.ext4 -q -F -d rootfs images/rootfs.ext4
sudo chown $USER images/rootfs.ext4
```

This study used Alpine minirootfs 3.24.3. The rootfs is attached read-only.

### 5. Prepare the traditional VM (T1)

```bash
REL=$(rpm -E %fedora)
BASE="https://download.fedoraproject.org/pub/fedora/linux/releases/$REL/Cloud/x86_64/images/"
IMG=$(curl -sL "$BASE" | grep -oP 'Fedora-Cloud-Base-Generic-[0-9][^"<>]*\.x86_64\.qcow2' | head -1)
curl -L -o images/fedora-cloud.qcow2 "$BASE$IMG"
virt-customize -a images/fedora-cloud.qcow2 \
  --uninstall cloud-init --root-password password:fedora --selinux-relabel

# Copy-on-write overlay for benchmarking (the base image is never modified)
qemu-img create -f qcow2 -b fedora-cloud.qcow2 -F qcow2 images/fedora-bench.qcow2
virt-customize -a images/fedora-bench.qcow2 \
  --upload boot-report.service:/etc/systemd/system/boot-report.service \
  --run-command 'systemctl enable boot-report.service' --selinux-relabel
```

The root password `fedora` is for a throwaway test VM with no network.

### 6. Run the benchmarks

```bash
sudo cpupower frequency-set -g performance
podman pull docker.io/library/alpine
I8042="i8042.noaux i8042.nomux i8042.nopnp i8042.dumbkbd"

# B1: boot latency
hyperfine --warmup 3 --runs 30 \
  --export-json logs/b1_main.json --export-markdown logs/b1_main.md \
  -n "T2 QEMU microvm" "./run_t2.sh quiet" \
  -n "T3 Firecracker default" "./run_t3.sh quiet" \
  -n "T3 Firecracker tuned" "./run_t3.sh quiet $I8042" \
  -n "T4 Podman container" "podman run --rm --network=none alpine true"

# Serial console cost
hyperfine --warmup 3 --runs 20 \
  --export-json logs/b1_console.json --export-markdown logs/b1_console.md \
  -n "T2 verbose" "./run_t2.sh" -n "T2 quiet" "./run_t2.sh quiet" \
  -n "T3 tuned verbose" "./run_t3.sh $I8042" -n "T3 tuned quiet" "./run_t3.sh quiet $I8042"

./bench_t1.sh | tee logs/b1_t1.txt               # B1 for T1
./bench_b2.sh | tee logs/b2_guest_init.csv        # B2: guest time to /init
sudo -v
./bench_b4.sh t2 | tee logs/b4_t2.txt             # B4: density + KSM
./bench_b4.sh t3 | tee logs/b4_t3.txt

sudo cpupower frequency-set -g powersave
```

**B3 (memory per instance)** is measured manually: start one VM in a second
terminal (`./run_t2.sh quiet mode=sleep`, `./run_t3.sh quiet mode=sleep $I8042`,
or `./run_t1.sh images/fedora-interactive.qcow2`), then record
`ps -o pid,rss,vsz,nlwp,comm -C qemu-system-x86_64` (or `-C firecracker`).
For the container, run `podman run -d --rm --name t4sleep alpine sleep 300`
and record `podman stats --no-stream t4sleep` and `ps -o pid,rss,comm -C conmon`.

### 7. Generate the charts

```bash
python3 plot.py
```

B3 and B4 values are entered at the top of `plot.py`; update them if you rerun.

## Configuration notes

- **QEMU microvm needs `pit=off,pic=off`** with this kernel. Otherwise the first
  timer interrupt arrives on vector 0 and the guest panics with a "divide error".
- **Firecracker's default boot is slowed by an i8042 probe** (about 0.48 s);
  the four `i8042.*` kernel options above remove it.
- **The rootfs is read-only** so every boot starts from an identical disk and
  no ext4 journal recovery runs.
- **Firecracker puts the terminal into raw mode**; Ctrl+C reaches the guest
  rather than stopping Firecracker. Use `pkill firecracker` from another
  terminal, then `reset`.

## Limitations

Results come from a single desktop machine; absolute numbers will differ on
other hardware. The microVM guest only prints a message and reboots. T1 was
measured over 5 runs. For KSM, the kernel's exact counters are the primary
evidence, since system-wide `free -m` figures were affected by desktop activity.

## References

- A. Agache et al., "Firecracker: Lightweight Virtualization for Serverless Applications," USENIX NSDI, 2020.
- F. Manco et al., "My VM is Lighter (and Safer) than your Container," ACM SOSP, 2017.
- K. Razavi et al., "Flip Feng Shui: Hammering a Needle in the Software Stack," USENIX Security, 2016.
- M. Shahrad et al., "Serverless in the Wild," USENIX ATC, 2020.
