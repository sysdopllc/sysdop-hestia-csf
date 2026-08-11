<?php
use function Hestiacp\quoteshellarg\quoteshellarg;

error_reporting(NULL);

$env = http_build_query($_GET);
if ($env == "") {
	$env = http_build_query($_POST);
}
$env .= "&HESTIASESSID=" . rawurlencode($_COOKIE["PHPSESSID"] ?? "");

include $_SERVER["DOCUMENT_ROOT"] . "/inc/main.php";

if (($_SESSION["role"] ?? "") !== "admin" || !empty($_SESSION["look"])) {
	header("Location: /list/user/");
	exit();
}

exec(HESTIA_CMD . "csf.pl " . quoteshellarg($env), $result, $return_var);

$header = 1;
foreach ($result as $line) {
	if ($header) {
		header("$line\n");
	} else {
		print "$line\n";
	}
	if ($header && $line == "") {
		$header = 0;
	}
}
