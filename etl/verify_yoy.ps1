# Queries the live model for every figure on page 05, Year on Year, for one year and comparison.
#
# The answer key is etl/yoy_expected.py, which gets the same figures from the CSVs in pandas.
# TREATAS pins the year and each button slicer the way the page does. The last block pins a
# filter-panel slicer too: an unfiltered check cannot catch a pool that ignores the panel.
#
#   powershell -File etl/verify_yoy.ps1 -Year 2023 -Comparison "Prior year"
#
# Run as a background job - closing the ADOMD connection can hang the shell.

param(
    [int]$Year = 2023,
    [string]$Comparison = "Prior year",
    [string]$Unit = "NEL"
)

$ErrorActionPreference = "Stop"

$msmdsrv = Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'"
if (-not $msmdsrv) { throw "msmdsrv.exe is not running - open the PBIP in Desktop first." }
$port = $null
foreach ($proc in $msmdsrv) {
    $conn = Get-NetTCPConnection -State Listen -OwningProcess $proc.ProcessId -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalAddress -eq "127.0.0.1" } | Select-Object -First 1
    if ($conn) { $port = $conn.LocalPort; break }
}
if (-not $port) { throw "could not find the local XMLA port" }

$pkg = (Get-AppxPackage -Name "*PowerBIDesktop*").InstallLocation
$adomd = @("Microsoft.PowerBI.AdomdClient.dll", "Microsoft.AnalysisServices.AdomdClient.dll") |
         ForEach-Object { Join-Path $pkg "bin\$_" } |
         Where-Object { Test-Path $_ } | Select-Object -First 1
[void][Reflection.Assembly]::LoadFrom($adomd)

$probe = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
$probe.Open()
$c = $probe.CreateCommand()
$c.CommandText = "SELECT [CATALOG_NAME] FROM `$SYSTEM.DBSCHEMA_CATALOGS"
$rd = $c.ExecuteReader(); $catalog = $null
if ($rd.Read()) { $catalog = $rd.GetString(0) }
$rd.Close(); $probe.Close()

$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection(
    "Data Source=localhost:$port;Initial Catalog=$catalog")
$conn.Open()

function Invoke-Dax($label, $dax) {
    Write-Output ""
    Write-Output "== $label"
    $cmd = $conn.CreateCommand()
    $cmd.CommandTimeout = 300
    $cmd.CommandText = $dax
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        $r = $cmd.ExecuteReader()
    } catch {
        Write-Output "   FAILED: $($_.Exception.InnerException.Message) $($_.Exception.Message)"
        return
    }
    $names = @(); for ($i = 0; $i -lt $r.FieldCount; $i++) { $names += $r.GetName($i) }
    Write-Output ("   " + ($names -join " | "))
    while ($r.Read()) {
        $vals = @()
        for ($i = 0; $i -lt $r.FieldCount; $i++) {
            $v = $r.GetValue($i)
            if ($v -is [double] -or $v -is [decimal]) { $v = [math]::Round([double]$v, 4) }
            $vals += "$v"
        }
        Write-Output ("   " + ($vals -join " | "))
    }
    $r.Close()
    Write-Output ("   ({0} ms)" -f $watch.ElapsedMilliseconds)
}

$pin = "TREATAS({$Year}, 'Date'[Year]), TREATAS({""$Comparison""}, 'YoY Comparison'[Comparison])"

$headline = @"
ROW(
        "Available", [YoY Comparison Available], "Months", [YoY Span],
        "Headcount", [YoY Headcount], "Headcount comp", [YoY Headcount Comparison],
        "Avg", [YoY Average Headcount], "Avg comp", [YoY Average Headcount Comparison],
        "Joiners", [YoY Joiners], "Joiners comp", [YoY Joiners Comparison],
        "Leavers", [YoY Leavers], "Leavers comp", [YoY Leavers Comparison],
        "Early share", [YoY Early Share], "Early share comp", [YoY Early Share Comparison],
        "Turnover", [YoY Turnover], "Turnover comp", [YoY Turnover Comparison],
        "Depts up", [Departments Up], "Depts", [Departments In Play],
        "Divisions up", [Divisions Up], "Divisions", [Divisions In Play]
    )
"@

Invoke-Dax "Headline: $Year against '$Comparison'" "EVALUATE CALCULATETABLE($headline, $pin)"

foreach ($metric in @("Headcount", "Joiners", "Leavers")) {
    Invoke-Dax "Monthly $metric" @"
EVALUATE
SUMMARIZECOLUMNS(
    'Date'[Month No], $pin, TREATAS({"$metric"}, 'YoY Chart Metric'[Metric]),
    "This", [YoY Chart This], "Comparison", [YoY Chart Comparison], "Change", [YoY Chart Change], "Colour", [YoY Chart Change Colour]
)
ORDER BY 'Date'[Month No]
"@
}

Invoke-Dax "Departments" @"
EVALUATE
SUMMARIZECOLUMNS(
    'Employee'[Department], $pin,
    "Headcount", [Dept Headcount], "Leavers", [Dept Leavers], "Was", [Dept Leavers Comparison],
    "Turnover", [Dept Turnover], "Turnover was", [YoY Turnover Comparison], "Change pp", [YoY Turnover Change pp],
    "Bar length", LEN([Dept Turnover Bar])
)
ORDER BY [Change pp] DESC
"@

foreach ($show in @("Top", "Bottom")) {
    Invoke-Dax "Divisions, $show 8" @"
EVALUATE
FILTER(
    SUMMARIZECOLUMNS(
        'Employee'[Division], $pin, TREATAS({"$show"}, 'Division Ranking'[Show]),
        "Rank", [Division Rank], "Leavers", [Division Leavers], "Was", [Division Leavers Comparison],
        "Change", [YoY Leaver Change], "Bar length", LEN([Division Leaver Bar])
    ),
    [Rank] <= 8
)
ORDER BY [Rank]
"@
}

Invoke-Dax "Words" @"
EVALUATE
CALCULATETABLE(
    UNION(
        ROW("Text", [YoY Standfirst]),
        ROW("Text", [YoY Title Line Chart] & " / " & [YoY Subtitle Line Chart]),
        ROW("Text", [YoY Title Variance Chart] & " / " & [YoY Subtitle Variance Chart]),
        ROW("Text", [YoY Title Department Table] & " / " & [YoY Subtitle Department Table]),
        ROW("Text", [YoY Title Division Table] & " / " & [YoY Subtitle Division Table]),
        ROW("Text", [YoY Filter Summary])
    ),
    $pin, TREATAS({"Leavers"}, 'YoY Chart Metric'[Metric])
)
"@

Invoke-Dax "SVG cards: length and head" @"
EVALUATE
CALCULATETABLE(
    UNION(
        ROW("Card", "Headcount", "Length", LEN([YoY Card Headcount]), "Head", LEFT([YoY Card Headcount], 60)),
        ROW("Card", "Leavers", "Length", LEN([YoY Card Leavers]), "Head", LEFT([YoY Card Leavers], 60)),
        ROW("Card", "Turnover", "Length", LEN([YoY Card Turnover]), "Head", LEFT([YoY Card Turnover], 60)),
        ROW("Card", "Divisions", "Length", LEN([YoY Card Divisions]), "Head", LEFT([YoY Card Divisions], 60))
    ),
    $pin
)
"@

Invoke-Dax "Panel slicer pinned: Business Unit = $Unit" @"
EVALUATE CALCULATETABLE(
    ADDCOLUMNS($headline, "Filter summary", [YoY Filter Summary]),
    $pin, TREATAS({"$Unit"}, 'Employee'[Business Unit])
)
"@

Invoke-Dax "Panel slicer pinned: departments under Business Unit = $Unit" @"
EVALUATE
SUMMARIZECOLUMNS(
    'Employee'[Department], $pin, TREATAS({"$Unit"}, 'Employee'[Business Unit]),
    "Leavers", [Dept Leavers], "Was", [Dept Leavers Comparison], "Change pp", [YoY Turnover Change pp]
)
ORDER BY [Change pp] DESC
"@

$conn.Close()
