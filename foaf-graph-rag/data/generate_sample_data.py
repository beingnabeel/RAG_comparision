"""Generate 100 realistic persons with relationships for the FoaF knowledge graph."""

import random
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

FOAF = Namespace("http://xmlns.com/foaf/0.1/")
REL = Namespace("http://purl.org/vocab/relationship/")
SCHEMA = Namespace("http://schema.org/")
CUSTOM = Namespace("http://example.org/foaf-poc/")

INDUSTRIES = [
    "Technology", "Healthcare", "Finance", "Education", "Manufacturing",
    "Retail", "Construction", "Transportation", "Energy", "Entertainment",
    "Legal", "Marketing", "Real Estate", "Agriculture", "Hospitality",
]

def generate_data():
    g = Graph()
    g.bind("foaf", FOAF)
    g.bind("rel", REL)
    g.bind("schema", SCHEMA)
    g.bind("custom", CUSTOM)

    persons = []
    person_names = []

    for i in range(1, 101):
        person_uri = CUSTOM[f"person{i:03d}"]
        persons.append(person_uri)

        gender = random.choice(["male", "female"])
        if gender == "male":
            first_name = fake.first_name_male()
        else:
            first_name = fake.first_name_female()
        last_name = fake.last_name()
        full_name = f"{first_name} {last_name}"
        person_names.append(full_name)

        # Basic info
        g.add((person_uri, RDF.type, CUSTOM.Person))
        g.add((person_uri, FOAF.name, Literal(full_name)))
        g.add((person_uri, FOAF.givenName, Literal(first_name)))
        g.add((person_uri, FOAF.familyName, Literal(last_name)))
        g.add((person_uri, FOAF.age, Literal(random.randint(18, 80), datatype=XSD.integer)))
        g.add((person_uri, FOAF.gender, Literal(gender)))
        g.add((person_uri, FOAF.phone, Literal(fake.phone_number())))
        g.add((person_uri, FOAF.mbox, URIRef(f"mailto:{first_name.lower()}.{last_name.lower()}@{fake.free_email_domain()}")))

        # Address
        city = fake.city()
        state = fake.state()
        postcode = fake.postcode()
        g.add((person_uri, SCHEMA.address, Literal(f"{fake.street_address()}, {city}, {state} {postcode}, USA")))
        g.add((person_uri, SCHEMA.addressLocality, Literal(city)))
        g.add((person_uri, SCHEMA.addressRegion, Literal(state)))
        g.add((person_uri, SCHEMA.postalCode, Literal(postcode)))
        g.add((person_uri, SCHEMA.addressCountry, Literal("USA")))

        # Occupation
        job = fake.job()
        g.add((person_uri, SCHEMA.jobTitle, Literal(job)))
        g.add((person_uri, CUSTOM.occupation, Literal(job)))
        g.add((person_uri, CUSTOM.industry, Literal(random.choice(INDUSTRIES))))

        # Timestamp
        g.add((person_uri, CUSTOM.createdAt, Literal("2025-02-06T10:00:00Z", datatype=XSD.dateTime)))

    # ── Relationships ────────────────────────────────────────────────────────

    # Track marriages to avoid polygamy in data
    married = set()

    for i, person in enumerate(persons):
        # Add 2-5 friendships per person
        num_friends = random.randint(2, 5)
        candidates = [j for j in range(len(persons)) if j != i]
        friends_idx = random.sample(candidates, min(num_friends, len(candidates)))
        for fi in friends_idx:
            g.add((person, REL.friendOf, persons[fi]))

        # 30% chance of being married (if not already)
        if i not in married and random.random() < 0.30:
            potential = [j for j in range(len(persons)) if j != i and j not in married and j > i]
            if potential:
                spouse_idx = random.choice(potential)
                g.add((person, REL.spouseOf, persons[spouse_idx]))
                g.add((persons[spouse_idx], REL.spouseOf, person))
                married.add(i)
                married.add(spouse_idx)

                # 60% chance married couple has 1-3 children
                if random.random() < 0.60:
                    num_children = random.randint(1, 3)
                    child_candidates = [j for j in range(len(persons)) if j != i and j != spouse_idx and j not in married]
                    children = random.sample(child_candidates, min(num_children, len(child_candidates)))
                    for ci in children:
                        g.add((person, REL.parentOf, persons[ci]))
                        g.add((persons[spouse_idx], REL.parentOf, persons[ci]))
                        g.add((persons[ci], REL.childOf, person))
                        g.add((persons[ci], REL.childOf, persons[spouse_idx]))

        # 20% chance of having a colleague relationship
        if random.random() < 0.20:
            colleague_idx = random.choice([j for j in range(len(persons)) if j != i])
            g.add((person, CUSTOM.colleagueOf, persons[colleague_idx]))

        # 15% chance of having a neighbor relationship
        if random.random() < 0.15:
            neighbor_idx = random.choice([j for j in range(len(persons)) if j != i])
            g.add((person, CUSTOM.neighborOf, persons[neighbor_idx]))

        # 10% chance of having a sibling
        if random.random() < 0.10:
            sibling_idx = random.choice([j for j in range(len(persons)) if j != i])
            g.add((person, REL.siblingOf, persons[sibling_idx]))
            g.add((persons[sibling_idx], REL.siblingOf, person))

    # Save
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data.ttl")
    g.serialize(destination=output_path, format="turtle")

    print(f"Generated {len(persons)} persons")
    print(f"Total triples: {len(g)}")
    print(f"Saved to: {output_path}")

    # Print some stats
    friendships = len(list(g.triples((None, REL.friendOf, None))))
    marriages = len(list(g.triples((None, REL.spouseOf, None))))
    parent_child = len(list(g.triples((None, REL.parentOf, None))))
    colleagues = len(list(g.triples((None, CUSTOM.colleagueOf, None))))
    neighbors = len(list(g.triples((None, CUSTOM.neighborOf, None))))
    siblings = len(list(g.triples((None, REL.siblingOf, None))))

    print(f"\nRelationship Stats:")
    print(f"  Friendships: {friendships}")
    print(f"  Marriages: {marriages} (pairs: {marriages // 2})")
    print(f"  Parent-Child: {parent_child}")
    print(f"  Colleagues: {colleagues}")
    print(f"  Neighbors: {neighbors}")
    print(f"  Siblings: {siblings}")


if __name__ == "__main__":
    generate_data()
