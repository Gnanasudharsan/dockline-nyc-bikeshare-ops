import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-[760px] px-4 pt-16">
      <h1 className="headline text-3xl">This page does not exist</h1>
      <p className="mt-4 text-slate">
        The link may be out of date. <Link href="/">Go to the live map</Link>.
      </p>
    </div>
  );
}
