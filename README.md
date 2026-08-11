# SYSDOP Hestia CSF

Kit interno para instalar o reparar CSF en HestiaCP sin confundir la integración
antigua de VestaCP con la identidad y las sesiones actuales de Hestia.

La fuente está fijada al release estable Aetherinox 15.10 y a su SHA-256 oficial.
No se aceptan ramas flotantes. El `main` evaluado el 11 de agosto de 2026 fue
rechazado porque `ServerCheck.pm` no superó la validación Perl después de
instalarse.

## Garantías

- verifica el archivo upstream antes de extraerlo;
- exige HestiaCP y `systemd`;
- descubre administrador renombrado, SSH, panel, FTP, pasivos, correo, DNS,
  QUIC, IPv6, Docker y rutas de logs;
- nunca abre backends Hestia, MySQL, Redis ni Memcached por inferencia;
- respalda CSF, la integración Hestia, unidades y reglas antes de escribir;
- neutraliza el comportamiento upstream que habilita CSF/LFD y apaga
  `firewalld`;
- autoriza la UI por rol administrativo, no por el nombre literal `admin`;
- preserva `csf.allow`, `csf.ignore` y regex personalizadas;
- desactiva actualizaciones y reinicios automáticos;
- termina con CSF y LFD deshabilitados e inactivos y `csf.disable` presente.

## Uso

Auditoría sin cambios:

```bash
sudo ./bin/sysdop-hestia-csf --audit
```

Aplicación:

```bash
sudo ./bin/sysdop-hestia-csf --apply
```

Para entornos sin salida a GitHub, transfiera primero el asset oficial y use:

```bash
sudo ./bin/sysdop-hestia-csf --apply --archive /root/csf-firewall-v15.10.tgz
```

El script no contiene una opción para activar el firewall. La activación futura
requiere un procedimiento separado, consola fuera de banda y pruebas de
conectividad.

## Pruebas locales

```bash
./tests/run.sh
```

Los fixtures simulan un Hestia con administrador y puertos renombrados, IPv6,
correo, DNS, FTP pasivo y el menú sin CSF. La prueba ejecuta dos veces los
parches y exige el mismo hash final.
