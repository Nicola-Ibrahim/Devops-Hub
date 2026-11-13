#!/usr/bin/env bash
set -Eeuo pipefail

mode="${1:-}"
case "${mode}" in
  --initialize-empty-volume|--mount-existing) ;;
  *) echo "Usage: initialize-data-volume.sh --initialize-empty-volume|--mount-existing" >&2; exit 2 ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
storage_helper="${script_dir}/helpers/configure_docker_storage.py"
if [[ ! -f "${storage_helper}" ]]; then
  storage_helper=/usr/local/lib/devops-hub/configure_docker_storage.py
fi
command -v python3 >/dev/null && [[ -r "${storage_helper}" ]] || {
  echo "Standalone Docker storage helper and Python 3 are required; no host changes made." >&2
  exit 1
}

volume_id_file=/etc/devops-hub/data-volume-id
if [[ ! -s "${volume_id_file}" ]]; then
  echo "Expected EBS volume ID file is missing; refusing to select a device by position." >&2
  exit 1
fi
volume_id="$(<"${volume_id_file}")"
if [[ ! "${volume_id}" =~ ^vol-[0-9a-f]+$ ]]; then
  echo "EBS volume ID is malformed; no device was changed." >&2
  exit 1
fi
device="/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${volume_id//-/}"
for attempt in $(seq 1 300); do
  [[ -b "${device}" ]] && break
  sleep 1
done
if [[ ! -b "${device}" ]]; then
  echo "The expected tagged EBS device is not attached; no other device was selected." >&2
  exit 1
fi
if mountpoint -q /srv/devops-hub-data; then
  mounted_uuid="$(findmnt -n -o UUID --target /srv/devops-hub-data)"
  device_uuid="$(blkid -s UUID -o value "${device}" || true)"
  [[ -n "${device_uuid}" && "${mounted_uuid}" == "${device_uuid}" ]] || {
    echo "A different device is mounted at the Docker data path; refusing to continue." >&2
    exit 1
  }
fi

filesystem="$(blkid -s TYPE -o value "${device}" 2>/dev/null || true)"
label="$(blkid -s LABEL -o value "${device}" 2>/dev/null || true)"
if [[ -z "${filesystem}" ]]; then
  if [[ "${mode}" != "--initialize-empty-volume" ]]; then
    echo "The expected volume is blank. Review the AWS volume ID, then explicitly initialize it." >&2
    exit 1
  fi
  signatures="$(wipefs --no-act --noheadings --output TYPE "${device}" | tr -d '[:space:]')"
  if [[ -n "${signatures}" ]]; then
    echo "Filesystem or partition signatures exist; refusing to format this volume." >&2
    exit 1
  fi
  mkfs.ext4 -F -L devops-hub-docker-data "${device}"
  filesystem=ext4
  label=devops-hub-docker-data
fi
if [[ "${filesystem}" != "ext4" || "${label}" != "devops-hub-docker-data" ]]; then
  echo "Expected ext4 volume label devops-hub-docker-data; refusing to overwrite existing data." >&2
  exit 1
fi

uuid="$(blkid -s UUID -o value "${device}")"
mount_path=/srv/devops-hub-data
data_root=${mount_path}/docker
if grep -Eq '[[:space:]]/srv/devops-hub-data[[:space:]]' /etc/fstab \
  && ! grep -Fq "UUID=${uuid} ${mount_path} ext4" /etc/fstab; then
  echo "A conflicting fstab entry exists; refusing to replace it." >&2
  exit 1
fi
if ! grep -Fq "UUID=${uuid} ${mount_path} ext4" /etc/fstab; then
  printf 'UUID=%s %s ext4 defaults 0 2\n' "${uuid}" "${mount_path}" >> /etc/fstab
fi

systemctl stop docker.service docker.socket 2>/dev/null || true
install -d -o root -g root -m 0755 "${mount_path}"
if ! mountpoint -q "${mount_path}"; then
  mount "${mount_path}"
fi
install -d -o root -g root -m 0711 "${data_root}"

python3 "${storage_helper}" "${data_root}"

install -d -o root -g root -m 0755 /etc/systemd/system/docker.service.d
cat >/etc/systemd/system/docker.service.d/10-devops-hub-data.conf <<'EOF'
[Unit]
RequiresMountsFor=/srv/devops-hub-data/docker
EOF
chmod 0644 /etc/systemd/system/docker.service.d/10-devops-hub-data.conf
systemctl daemon-reload
systemctl enable --now docker.service
docker info --format '{{.DockerRootDir}}' | grep -Fxq "${data_root}"
echo "Persistent Docker data volume is mounted and Docker uses the protected EBS data root."
