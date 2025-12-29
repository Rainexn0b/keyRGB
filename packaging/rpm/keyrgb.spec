Name:           keyrgb
Version:        0.2.1
Release:        1%{?dist}
Summary:        Minimal RGB keyboard controller for ITE 8291 keyboards

License:        GPL-2.0-or-later
URL:            https://github.com/Rainexn0b/keyRGB

Source0:        https://github.com/Rainexn0b/keyRGB/archive/refs/tags/v%{version}.tar.gz
Source1:        https://github.com/pobrn/ite8291r3-ctl/archive/refs/heads/master.tar.gz

Patch1:         ite8291r3-ctl-wootbook-support.patch

# This spec is intended for COPR or local builds.
# It installs KeyRGB (pyproject.toml) and builds/installs upstream ite8291r3-ctl
# as a bundled dependency. A small patch is applied to support Wootbook (0x600B).

%global ite_upstream_dir ite8291r3-ctl-master

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
BuildRequires:  pyproject-rpm-macros

Requires:       python3-pystray
Requires:       python3-pillow
Requires:       python3-pyusb

%description
KeyRGB is a Linux tray app + per-key editor for laptop keyboards driven by ITE 8291 / ITE8291R3-style controllers.

%prep
%autosetup -n keyRGB-%{version}

# Unpack upstream ite8291r3-ctl source (Source1) and apply the Wootbook patch.
tar -xf %{SOURCE1}
pushd %{ite_upstream_dir}
patch -p1 -i %{PATCH1}
popd

%build
# Build the main KeyRGB wheel
%pyproject_wheel

%install
# Install KeyRGB
%pyproject_install

# Install upstream ite8291r3-ctl module (setup.py based), patched for Wootbook.
pushd %{ite_upstream_dir}
%{python3} -m pip install . \
  --root %{buildroot} \
  --prefix %{_prefix} \
  --no-deps \
  --no-build-isolation \
  --disable-pip-version-check
popd

# udev rule for non-root access
install -D -m 0644 packaging/udev/99-ite8291-wootbook.rules %{buildroot}%{_udevrulesdir}/99-ite8291-wootbook.rules

%check
# Basic import smoke test (no hardware)
%{python3} -c "import src.gui.tray"
%{python3} -c "import ite8291r3_ctl"
%{python3} -c "from ite8291r3_ctl import ite8291r3 as m; assert 0x600B in m.PRODUCT_IDS"

%files
%license LICENSE
%doc README.md
%{_udevrulesdir}/99-ite8291-wootbook.rules

# KeyRGB python package(s) installed via pyproject
%pyproject_files

# Bundled ite8291r3-ctl python module installed via setup.py
%{python3_sitelib}/ite8291r3_ctl*

%changelog
* Mon Dec 29 2025 KeyRGB Contributors - 0.2.1-1
- Docs/screenshots update

* Mon Dec 29 2025 KeyRGB Contributors - 0.2.0-1
- Release v0.2.0

* Mon Dec 29 2025 KeyRGB Contributors - 0.1.5-1
- Release v0.1.5

* Sun Dec 28 2025 KeyRGB Contributors - 0.1.4-1
- Tray + GUI integration updates
