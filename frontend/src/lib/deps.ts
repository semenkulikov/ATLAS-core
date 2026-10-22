/** Package name lives on the predicate. The value is a version or an unpinned note. */

export function dependencyParts(
  predicate: string,
  value: string,
): { name: string; unpinned: boolean; detail: string } {
  const name = predicate.startsWith("dependency.") ? predicate.slice("dependency.".length) : predicate;
  const unpinned = value.toLowerCase().includes("not pinned");
  return { name, unpinned, detail: unpinned ? "" : value };
}
