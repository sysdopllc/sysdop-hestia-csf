	# SYSDOP_HESTIA_REGEX_BEGIN
	# HestiaCP auth.log: YYYY-MM-DD HH:MM:SS username address failed to login
	if (
		($globlogs{@@CUSTOM_LOG@@}{$lgfile}) and
		($line =~ /^\S+\s+\S+\s+(\S+)\s+([0-9A-Fa-f:.]+)\s+failed to login\s*$/)
	) {
		my $account = $1;
		my $ip = $2;
		$ip =~ s/^::ffff://;
		return (
			"Failed HestiaCP login from",
			"$ip|$account",
			"hestia",
			"5",
			"@@HESTIA_PORT@@",
			"1",
			"0",
		);
	}
	# SYSDOP_HESTIA_REGEX_END
