Name:           keyrgb
Version:        1.0.0
Release:        1%{?dist}
Summary:        Minimal RGB keyboard controller for ITE 8291 keyboards

License:        GPL-2.0-only
URL:            https://github.com/Rainexn0b/keyRGB

Source0:        %{name}-%{version}.tar.gz

# This spec is intended for COPR or local builds.
# It installs KeyRGB (pyproject.toml) and the vendored ite8291r3-ctl python module.

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
BuildRequires:  pyproject-rpm-macros

Requires:       python3-pystray
Requires:       python3-pillow
Requires:       python3-pyusb

%description
KeyRGB is a Linux tray app + per-key editor for laptop keyboards driven by ITE 8291 / ITE8291R3-style controllers.

%prep
%autosetup -n %{name}-%{version}

%build
# Build the main KeyRGB wheel
%pyproject_wheel

%install
# Install KeyRGB
%pyproject_install

# Install vendored ite8291r3-ctl module (setup.py based)
# This keeps the modified version bundled with the RPM.
pushd ite8291r3-ctl
%{python3} setup.py install --skip-build --root %{buildroot} --prefix %{_prefix}
popd

# udev rule for non-root access
install -D -m 0644 packaging/udev/99-ite8291-wootbook.rules %{buildroot}%{_udevrulesdir}/99-ite8291-wootbook.rules

%check
# Basic import smoke test (no hardware)
%{python3} -c "import src.gui.tray"
%{python3} -c "import ite8291r3_ctl"

%files
%license LICENSE
%doc README.md
%{_udevrulesdir}/99-ite8291-wootbook.rules

# KeyRGB python package(s) installed via pyproject
%pyproject_files

# Vendored ite8291r3-ctl python module installed via setup.py
%{python3_sitelib}/ite8291r3_ctl*

%changelog
* Thu Dec 25 2025 KeyRGB Contributors - 1.0.0-1
- Initial RPM packaging for COPR/local installs
