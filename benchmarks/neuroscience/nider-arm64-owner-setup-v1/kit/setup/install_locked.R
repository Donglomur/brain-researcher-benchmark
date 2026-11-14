# Future offline provisioning only. This file has not been executed.
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 5L, identical(as.character(getRversion()), "4.3.2"))
plan <- utils::read.delim(args[[1]], colClasses = "character", check.names = FALSE,
                         quote = "", na.strings = NULL)
sources <- utils::read.delim(args[[2]], colClasses = "character", check.names = FALSE,
                            quote = "", na.strings = NULL)
stopifnot(identical(names(plan), c("Package", "Version", "Requires")),
          identical(names(sources), c("Package", "Version", "Filename", "SHA256", "Bytes", "SourceURL")),
          nrow(plan) == 68L, nrow(sources) == 68L,
          !anyDuplicated(plan$Package), !anyDuplicated(sources$Package),
          setequal(plan$Package, sources$Package),
          all(grepl("^[A-Za-z][A-Za-z0-9.]*$", plan$Package)),
          all(grepl("^[0-9][0-9A-Za-z.-]*$", plan$Version)))
sources <- sources[match(plan$Package, sources$Package), , drop = FALSE]
stopifnot(identical(plan$Version, sources$Version),
          identical(sources$Filename, paste0(plan$Package, "_", plan$Version, ".tar.gz")),
          all(grepl("^[0-9a-f]{64}$", sources$SHA256)),
          all(grepl("^[0-9]+$", sources$Bytes)),
          all(as.numeric(sources$Bytes) > 0 & as.numeric(sources$Bytes) <= 104857600),
          all(startsWith(sources$SourceURL, "https://")))
archive_dir <- normalizePath(args[[3]], mustWork = TRUE)
library_dir <- normalizePath(args[[4]], mustWork = TRUE)
receipt_dir <- normalizePath(args[[5]], mustWork = TRUE)
.libPaths(c(library_dir, .Library))
stopifnot(identical(.libPaths()[[1]], library_dir))
# Full archive bytes are authenticated before any installation.
for (i in seq_len(nrow(sources))) {
  archive <- file.path(archive_dir, sources$Filename[[i]])
  stopifnot(file.exists(archive), !dir.exists(archive),
            identical(Sys.readlink(archive), "") || is.na(Sys.readlink(archive)),
            file.info(archive)$size == as.numeric(sources$Bytes[[i]]))
  line <- system2("sha256sum", shQuote(archive), stdout = TRUE)
  status <- attr(line, "status")
  stopifnot(is.null(status) || status == 0L, length(line) == 1L,
            identical(substr(line, 1L, 64L), sources$SHA256[[i]]))
}
# Requirements are the exact conservative 68-record lock closure. All are
# installed in the isolated library, including matching recommended packages.
remaining <- plan$Package
ordered <- character()
while (length(remaining)) {
  available <- remaining[vapply(remaining, function(package) {
    dependencies <- strsplit(plan$Requires[match(package, plan$Package)], ",", fixed = TRUE)[[1]]
    !any(dependencies[nzchar(dependencies)] %in% remaining)
  }, logical(1))]
  stopifnot(length(available) > 0L)
  package <- sort(available)[[1]]
  ordered <- c(ordered, package)
  remaining <- setdiff(remaining, package)
}
for (package in ordered) {
  i <- match(package, plan$Package)
  archive <- file.path(archive_dir, sources$Filename[[i]])
  utils::install.packages(archive, repos = NULL, type = "source", dependencies = FALSE,
                          lib = library_dir, Ncpus = 1L, quiet = FALSE)
  actual <- utils::packageDescription(package, lib.loc = library_dir, fields = "Version")
  stopifnot(identical(actual, plan$Version[[i]]))
}
installed <- data.frame(Package = plan$Package, Version = vapply(plan$Package, function(package) {
  utils::packageDescription(package, lib.loc = library_dir, fields = "Version")
}, character(1)), stringsAsFactors = FALSE)
stopifnot(identical(installed$Version, plan$Version))
utils::write.table(installed, file.path(receipt_dir, "package-versions.tsv"),
                   row.names = FALSE, quote = TRUE, sep = "\t")
writeLines(capture.output(utils::sessionInfo()), file.path(receipt_dir, "session-info.txt"))
writeLines(ordered, file.path(receipt_dir, "installation-order.txt"))
# Runtime image ID, R/Rscript/R-home/installed-library tree hashes and external
# original stdout/stderr/exit remain the owner's required post-build evidence.

