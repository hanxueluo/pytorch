from abc import abstractmethod
from typing import Any, Dict, List, Optional


class TestPrioritizations:
    """
    Describes the results of whether heuristics consider a test relevant or not.

    Special meanings:
    - Heuristics can leave a list empty if they don't consider any tests to be in that category
    - Heuristics can leave the unranked_relevance list empty to imply all unmentioned tests are irrelevant

    Important: Lists of tests must always be returned in a deterministic order,
               otherwise it breaks the test sharding logic
    """

    highly_relevant: List[str]
    probably_relevant: List[str]
    # For when we don't know if the test is relevant to the PR or not
    unranked_relevance: List[str]
    # future cateories could include 'definitely not relevant' and 'probably not relevant'

    def __init__(
        self,
        highly_relevant: Optional[List[str]] = None,
        probably_relevant: Optional[List[str]] = None,
        unranked_relevance: Optional[List[str]] = None,
    ) -> None:
        self.highly_relevant = highly_relevant or []
        self.probably_relevant = probably_relevant or []
        self.unranked_relevance = unranked_relevance or []

    @staticmethod
    def _merge_tests(
        current_tests: List[str],
        new_tests: List[str],
        exclude_tests: List[str],
        orig_tests: List[str],
    ) -> List[str]:
        """
        We append all new tests to the current tests, while preserving the sorting on the new_tests
        However, exclude any specified tests which have now moved to a higher priority list or tests
        that weren't originally in the self's TestPrioritizations
        """
        current_tests.extend(new_tests)
        current_tests = [
            test
            for test in current_tests
            if test not in exclude_tests and test in orig_tests
        ]  # skip the excluded tests
        current_tests = list(dict.fromkeys(current_tests))  # remove dupes

        return current_tests

    def integrate_priorities(self, other: "TestPrioritizations") -> None:
        """
        Integrates priorities from another TestPrioritizations object.

        The final result takes all tests from the `self` and rearranges them based on priorities from `other`.
        If there are tests mentioned in `other` which are not in `self`, those tests are ignored.
        (For example, that can happen if a heuristic reports tests that are not run in the current job)
        """
        orig_tests = (
            self.highly_relevant + self.probably_relevant + self.unranked_relevance
        )

        # only add new tests to the list, while preserving the sorting
        self.highly_relevant = TestPrioritizations._merge_tests(
            self.highly_relevant,
            other.highly_relevant,
            exclude_tests=[],
            orig_tests=orig_tests,
        )

        self.probably_relevant = TestPrioritizations._merge_tests(
            self.probably_relevant,
            other.probably_relevant,
            exclude_tests=self.highly_relevant,
            orig_tests=orig_tests,
        )

        # Remove any tests that are now in a higher priority list
        self.unranked_relevance = TestPrioritizations._merge_tests(
            self.unranked_relevance,
            new_tests=[],
            exclude_tests=(self.highly_relevant + self.probably_relevant),
            orig_tests=orig_tests,
        )

    def find_conflicts(self) -> List[str]:
        """
        Returns a list of tests which are in multiple lists.
        """
        tests = self.highly_relevant + self.probably_relevant + self.unranked_relevance
        return [test for test in tests if tests.count(test) > 1]

    def get_unexpected_tests(self, expected: List[str]) -> List[str]:
        """
        Returns a list of tests which are not in the expected list.
        """
        tests = self.highly_relevant + self.probably_relevant + self.unranked_relevance
        return [test for test in tests if test not in expected]

    def print_info(self, expected: List[str]) -> None:
        def _print_tests(label: str, tests: List[str]) -> None:
            if not tests:
                return

            print(f"{label} tests ({len(tests)}):")
            for test in tests:
                if test in tests:
                    print(f"  {test}")

        _print_tests("Highly relevant", self.highly_relevant)
        _print_tests("Probably relevant", self.probably_relevant)
        _print_tests("Unranked relevance", self.unranked_relevance)

        conflicts = self.find_conflicts()
        if conflicts:
            print(f"WARNING: {len(conflicts)} tests are in multiple lists:")
            for test in conflicts:
                lists = []
                for list_name in ["highly_relevant", "probably_relevant", "unranked"]:
                    if test in getattr(self, list_name):
                        lists.append(list_name)
                print(f"  {test} is in {' ,'.join(lists)}")
        else:
            print("No conflicts found")

        unexpected = self.get_unexpected_tests(expected)
        if unexpected:
            print(f"WARNING: {len(unexpected)} tests are not in the expected list:")
            for test in unexpected:
                print(f"  {test}")
        else:
            print("No unexpected tests found")


class HeuristicInterface:
    """Interface for all heuristics."""

    name: str
    description: str

    @abstractmethod
    def __init__(self, **kwargs: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_test_priorities(self, tests: List[str]) -> TestPrioritizations:
        pass

    def __str__(self) -> str:
        # returns the concrete class's name, and optionally any constructor arguments params

        return self.__class__.__name__
