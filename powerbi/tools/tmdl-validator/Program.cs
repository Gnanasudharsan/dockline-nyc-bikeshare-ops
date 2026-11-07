// Usage: dotnet run -- <path to *.SemanticModel/definition>
// Exit code 0 when the TMDL folder deserializes into a valid Tabular model.
using Microsoft.AnalysisServices.Tabular;

if (args.Length != 1)
{
    Console.Error.WriteLine("usage: TmdlValidator <SemanticModel/definition folder>");
    return 2;
}

try
{
    var database = TmdlSerializer.DeserializeDatabaseFromFolder(args[0]);
    var model = database.Model;
    var measures = model.Tables.Sum(t => t.Measures.Count);
    Console.WriteLine($"OK: '{database.Name}' compatibility {database.CompatibilityLevel}");
    Console.WriteLine($"    tables {model.Tables.Count}, measures {measures}, relationships {model.Relationships.Count}, roles {model.Roles.Count}, expressions {model.Expressions.Count}");
    foreach (var table in model.Tables)
    {
        Console.WriteLine($"    {table.Name}: {table.Columns.Count(c => c.Type != ColumnType.RowNumber)} columns, {table.Measures.Count} measures, partitions {string.Join(",", table.Partitions.Select(p => p.Mode))}");
    }
    return 0;
}
catch (Exception error)
{
    Console.Error.WriteLine($"TMDL ERROR: {error.GetType().Name}: {error.Message}");
    if (error.InnerException is not null)
    {
        Console.Error.WriteLine($"  inner: {error.InnerException.Message}");
    }
    return 1;
}
