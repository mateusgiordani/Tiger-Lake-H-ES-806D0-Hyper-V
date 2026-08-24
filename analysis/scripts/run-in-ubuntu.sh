#!/usr/bin/env bash
# run-in-ubuntu.sh — Coleta de evidencia Tiger Lake na sessao Linux (Polestar HM570).
#
# Somente leitura: nao escreve MSR, nao altera configuracao de firmware,
# nao instala nada e nao reinicializa. Seguro para rodar em qualquer Ubuntu.
#
# Uso (na sessao Ubuntu):
#   sudo bash run-in-ubuntu.sh
#
# Saida: ./tgl-linux-evidence-AAAAMMDD-HHMMSS.tar.gz
# Trazer o .tar.gz de volta para o Windows em analysis/linux-msr/.

set -u

OUT="tgl-linux-evidence-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT" || exit 1
echo "[*] Diretorio de saida: $OUT"

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "[!] Rode com sudo: a leitura de /dev/cpu/*/msr exige privilegio." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTOR="$SCRIPT_DIR/collect_tgl_vmx_msrs_linux.py"

if [ ! -f "$COLLECTOR" ]; then
  COLLECTOR="./collect_tgl_vmx_msrs_linux.py"
fi
if [ ! -f "$COLLECTOR" ]; then
  echo "[!] Coletor collect_tgl_vmx_msrs_linux.py nao encontrado ao lado deste script." >&2
  exit 1
fi

echo "[*] Carregando modulo msr..."
modprobe msr 2>"$OUT/modprobe-msr.err" || echo "[!] modprobe msr falhou (seguindo; leituras podem falhar)"

echo "[*] Identificacao do sistema..."
{
  uname -a
  cat /etc/os-release 2>/dev/null
  echo "cmdline: $(cat /proc/cmdline)"
} > "$OUT/system.txt" 2>&1

echo "[*] Coletando MSRs VMX por processador logico (somente leitura)..."
python3 "$COLLECTOR" > "$OUT/tgl-vmx-msrs.json" 2> "$OUT/tgl-vmx-msrs.stderr.txt"
echo "[*] Coletor terminou com codigo $?"

echo "[*] Topologia e cpuinfo completos..."
cp /proc/cpuinfo "$OUT/cpuinfo.txt" 2>/dev/null
lscpu > "$OUT/lscpu.txt" 2>&1
lscpu -e=CPU,CORE,SOCKET,NODE,ONLINE,MAXMHZ,MINMHZ > "$OUT/lscpu-extended.txt" 2>&1

echo "[*] Microcode por CPU..."
for c in /sys/devices/system/cpu/cpu*; do
  name="$(basename "$c")"
  ver=""
  for f in version processor_version revision; do
    if [ -r "$c/microcode/$f" ]; then
      ver="$(cat "$c/microcode/$f" 2>/dev/null)"
      [ -n "$ver" ] && break
    fi
  done
  echo "$name: ${ver:-desconhecido}"
done > "$OUT/microcode-per-cpu.txt"

dmesg 2>/dev/null | grep -iE 'microcode|vmx|kvm|apic|x2apic|mce|mcheck'   > "$OUT/dmesg-microcode-vmx-apic.txt"

echo "[*] Informacoes de BIOS/placa via dmidecode..."
dmidecode -t bios -t baseboard -t processor > "$OUT/dmidecode.txt" 2>&1

echo "[*] Tabelas ACPI vistas pelo Linux (bonus, se acpica-tools existir)..."
if command -v acpidump >/dev/null 2>&1; then
  acpidump > "$OUT/acpi_tables.dat" 2>"$OUT/acpidump.stderr.txt"
  ( cd "$OUT" && acpixtract -a acpi_tables.dat > acpixtract.log 2>&1 ) || true
else
  echo "acpidump ausente; opcional: sudo apt install acpica-tools" > "$OUT/acpidump.ausente"
fi

echo "[*] Empacotando..."
tar czf "$OUT.tar.gz" "$OUT" 2>/dev/null
echo "[+] Concluido: $PWD/$OUT.tar.gz"
echo "    Guarde este arquivo e leve-o de volta ao Windows:"
echo "    extrair dentro de analysis/linux-msr/."
