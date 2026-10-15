#!/usr/bin/env python3
"""claude-first.vsix を作る（Node の道具なしで。package.json と extension.js を詰めるだけ）"""
import json, zipfile, pathlib
here = pathlib.Path(__file__).resolve().parent
pkg = json.loads((here / "package.json").read_text(encoding="utf-8"))
manifest = f'''<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="{pkg['name']}" Version="{pkg['version']}" Publisher="{pkg['publisher']}"/>
    <DisplayName>{pkg['displayName']}</DisplayName>
    <Description xml:space="preserve">{pkg['description']}</Description>
    <Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="{pkg['engines']['vscode']}"/></Properties>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation>
  <Dependencies/>
  <Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/></Assets>
</PackageManifest>'''
ct = ('<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension=".json" ContentType="application/json"/><Default Extension=".js" ContentType="application/javascript"/>'
      '<Default Extension=".vsixmanifest" ContentType="text/xml"/></Types>')
with zipfile.ZipFile(here / "claude-first.vsix", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", ct)
    z.writestr("extension.vsixmanifest", manifest)
    for f in ("package.json", "extension.js"):
        z.write(here / f, f"extension/{f}")
print("built", pkg["version"])
