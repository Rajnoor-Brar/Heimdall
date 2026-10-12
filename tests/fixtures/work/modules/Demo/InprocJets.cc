// modules/Demo/InprocJets.cc — Pythia and Rivet in one process: an integrated run.
// requires: pythia8 rivet fastjet   (Module.hh adds hepmc3 toml; Inproc/Analysis.hh uses FastJet and SISCone)
//
//     InprocJets.exe CONFIG.toml --output=jets.yoda
//
// The chain App_Pythia → FIFO → rivet as one program, with no HepMC text between the two
// (docs/06_Internals.md §21). It reads Pythia's card and Rivet's analyses from the point's context file
// (04 §9.4), so the runner still owns the sweeps, seeds and cards, and this program only runs them:
//
//     [run.cfgs.inproc]
//     tools          = ["jets", "yd2rt"]
//     generate_cards = ["pythia", "rivet"]   # not run: the card App_Pythia would get (seeds included),
//                                            # the rivet table's analyses (options included), the plugin path
//     [tools.jets]
//     tool           = "module"
//     executable     = "InprocJets.exe"
//     output_file    = "jets.yoda"
//
// Config ([tools.<tag>.config]):
//   engine        = "parallel"  PythiaParallel as App_Pythia runs it: the same card, seeds and instances
//                   "serial"    one Pythia8::Pythia, seeded by the card's Random:seed
//   rivet_threads = 1           Rivets, each on its own thread, merged at the end (V34); above 1 it
//                               needs the SISCone patch (L29) and refuses to run without it
//
// Threads: the card's Parallelism:numThreads generate and convert, and rivet_threads analyse. The
// pieces are in Inproc/: Stamp.hh (numbering and σ: L1, L2, L28), Feed.hh (Pythia threads → the
// Rivets), Analysis.hh (the Rivets and their merge: L16, L29), Engines.hh (serial and parallel: L3,
// L5, L6).

#include "Module.hh"
#include "Inproc/Analysis.hh"
#include "Inproc/Engines.hh"
#include "Inproc/Stamp.hh"

#include <string>

int main(int argc, char** argv) {
    Module::Job job(argc, argv);
    const std::string engine = job.setting("engine", "parallel", "parallel: PythiaParallel, as App_Pythia; serial: one Pythia");
    const int rivetThreads = job.setting("rivet_threads", 1, "Rivets on threads of their own, merged at the end (V34, L29)");
    if (job.hasInput()) job.fail(Module::Usage, "InprocJets makes its own events; give it no input");
    if (engine != "parallel" && engine != "serial") job.fail(Module::Config, "engine must be parallel or serial");
    const std::string card = job.card("pythia");                    // the context file's (generate_cards)

    Inproc::Analysis rivet(job, job.tool("rivet"), rivetThreads);
    Inproc::Stamper stamper;
    const Inproc::Run run = engine == "serial" ? Inproc::serial(job, card, stamper, rivet)
                                               : Inproc::parallel(job, card, stamper, rivet);
    if (!run.error.empty()) {
        rivet.halt();                                               // no thread may outlive the exit
        job.fail(Module::Internal, run.error);
    }
    if (const std::string error = rivet.finish(Inproc::lastSigma(stamper), job.output()); !error.empty())
        job.fail(Module::Output, error);                            // the YODA could not be written (06 §11)

    job.setCrossSection(run.sigma.pb, run.sigma.errPb, "generator");   // the report's σ: the run's own
    job.status().xsec(run.sigma.pb, run.sigma.errPb, true);
    return job.finish();
}
