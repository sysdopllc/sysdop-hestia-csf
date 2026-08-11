#!/bin/sh
if test `cat /proc/1/comm` = "systemd"; then
	info "    Enabling systemctl services ${bluel}csf.service${greym} and ${bluel}lfd.service${greym}"
    run systemctl enable csf.service
    run systemctl enable lfd.service

	info "    Disabling systemctl service ${bluel}firewalld${greym}"
    run systemctl disable firewalld
    run systemctl stop firewalld
    run systemctl mask firewalld
fi
