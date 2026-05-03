param(
    [Parameter(ValueFromPipeline = $true)]
    [string]$Text
)

begin {
    $buffer = New-Object System.Collections.Generic.List[string]
}

process {
    if ($null -ne $Text) {
        $buffer.Add($Text)
    }
}

end {
    $all = ($buffer -join "`n").Trim()
    if ([string]::IsNullOrWhiteSpace($all)) {
        throw "No text provided on stdin."
    }
    & "$PSScriptRoot\speak.ps1" -Text $all
}
