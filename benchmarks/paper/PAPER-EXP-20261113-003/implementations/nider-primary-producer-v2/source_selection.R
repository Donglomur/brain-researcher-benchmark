# Parsing only. This helper never evaluates the parsed author source.
allowed_spans <- function() {
  single <- function(n) c(n, n)
  c(lapply(13:19, single), list(c(28, 28), c(29, 29), c(73, 73), c(74, 74), c(75, 75),
    c(77, 82), c(86, 129), c(131, 138), c(140, 140), c(141, 141), c(149, 149),
    c(153, 153), c(216, 216), c(219, 219), c(262, 262), c(265, 265)))
}

select_source_expressions <- function(expressions, manifest) {
  expected <- allowed_spans()
  need(length(manifest) == length(expected), "exact expression manifest length required")
  references <- attr(expressions, "srcref")
  selected <- vapply(seq_along(expected), function(i) {
    span <- manifest[[i]]
    need(identical(as.numeric(c(span$start, span$end)), as.numeric(expected[[i]])), "exact expression span required")
    found <- which(vapply(references, function(ref) ref[1L] == span$start &&
                           ref[3L] == span$end, logical(1)))
    need(length(found) == 1L, "allowlist must match a complete unique top-level expression")
    found
  }, integer(1))
  need(!anyDuplicated(selected) && identical(selected, sort(selected)), "ordered expressions required")
  selected
}
