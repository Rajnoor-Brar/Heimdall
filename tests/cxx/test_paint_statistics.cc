// tests/cxx/test_paint_statistics.cc — src/Apps/Paint/Transform.hh's statistics (V160): a curve's area, and its
// area and χ² against a reference, over the drawn range, on the reference's bins.
// requires: none

#include "Apps/Paint/Transform.hh"

#include <cmath>
#include <cstdio>

static int failures = 0;
#define CHECK(cond)                                                                   \
    do {                                                                              \
        if (!(cond)) {                                                                \
            std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);      \
            ++failures;                                                               \
        }                                                                             \
    } while (0)

static bool near(double a, double b) { return std::fabs(a - b) <= 1e-9 * std::max(1.0, std::fabs(b)); }

static Paint::Series series(std::vector<double> edges, std::vector<double> y, std::vector<double> err) {
    Paint::Series s;
    for (size_t i = 0; i + 1 < edges.size(); ++i) s.lo.push_back(edges[i]), s.hi.push_back(edges[i + 1]);
    s.y = y, s.err = err;
    return s;
}

int main() {
    const auto mc = series({0, 1, 2, 3, 4}, {1, 2, 3, 4}, {0.1, 0.1, 0.1, 0.1});
    const auto same = Paint::statistics(mc, mc, 0, 4);                   // against itself: nothing apart
    CHECK(same.bins == 4 && near(same.area, 10) && near(same.areaErr, 0.2));
    CHECK(near(same.refArea, 10) && near(same.absArea, 0) && near(same.chi2, 0) && same.ndf == 4);

    const auto data = series({1, 3}, {2.0}, {0.5});                      // one wide bin over MC's 2nd and 3rd
    const auto s = Paint::statistics(mc, data, 0, 4);
    CHECK(s.compared == 1 && near(s.refArea, 4) && near(s.absArea, 1.0));   // MC rebinned: 2.5 over 2 units
    const double sigma2 = std::pow(std::sqrt(0.1 * 0.1 + 0.1 * 0.1) / 2, 2) + 0.25;
    CHECK(near(s.chi2, 0.25 / sigma2) && s.ndf == 1);

    const auto inside = Paint::statistics(mc, mc, 1, 3);                 // the drawn range only
    CHECK(inside.bins == 2 && near(inside.area, 5));

    auto voided = mc;
    voided.y[0] = std::nan("");                                          // a voided bin counts for nothing
    const auto v = Paint::statistics(voided, mc, 0, 4);
    CHECK(v.bins == 3 && near(v.area, 9) && v.compared == 3);

    const auto uncovered = series({0.5, 1.5}, {1.0}, {0.0});             // no exact cover: not compared
    CHECK(Paint::statistics(mc, uncovered, 0, 4).compared == 0);

    if (failures) std::fprintf(stderr, "%d failure(s)\n", failures);
    else std::printf("ok\n");
    return failures ? 1 : 0;
}
