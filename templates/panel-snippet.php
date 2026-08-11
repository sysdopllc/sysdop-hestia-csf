							<!-- SYSDOP Hestia CSF integration -->
							<?php if (($_SESSION["userContext"] ?? "") === "admin" && empty($_SESSION["look"])) { ?>
								<li class="top-bar-menu-item">
									<a title="<?= _("CSF Firewall") ?>" class="top-bar-menu-link <?php if ($TAB == "CSF") {
										echo "active";
									} ?>" href="/list/csf/">
										<i class="fas fa-shield-alt"></i>
										<span class="top-bar-menu-link-label u-hide-desktop"><?= _("CSF Firewall") ?></span>
									</a>
								</li>
							<?php } ?>
